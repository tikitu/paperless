import datetime
import imaplib
import os
import re
import time

from base64 import b64decode
from email import policy
from email.parser import BytesParser
from dateutil import parser

from django.conf import settings

from logger.models import Log

from .consumer import Consumer
from .models import Sender


class MailFetcherError(Exception):
    pass


class InvalidMessageError(Exception):
    pass


class Message(object):
    """
    A crude, but simple email message class.  We assume that there's a subject
    and n attachments, and that we don't care about the message body.
    """

    SECRET = settings.UPLOAD_SHARED_SECRET

    def __init__(self, data, verbosity=1):
        """
        Cribbed heavily from
        https://www.ianlewis.org/en/parsing-email-attachments-python
        """

        self.verbosity = verbosity

        self.subject = None
        self.time = None
        self.attachment = None

        message = BytesParser(policy=policy.default).parsebytes(data)
        self.subject = str(message["Subject"]).replace("\r\n", "")
        self.body = str(message.get_body())

        self.check_subject()
        self.check_body()

        self._set_time(message)

        Log.info(
            'Importing email: "{}"'.format(self.subject), Log.COMPONENT_MAIL)

        attachments = []
        for part in message.walk():

            content_disposition = part.get("Content-Disposition")
            if not content_disposition:
                continue

            dispositions = content_disposition.strip().split(";")
            if not dispositions[0].lower() == "attachment":
                continue

            file_data = part.get_payload()

            attachments.append(Attachment(
                b64decode(file_data), content_type=part.get_content_type()))

        if len(attachments) == 0:
            raise InvalidMessageError(
                "There don't appear to be any attachments to this message")

        if len(attachments) > 1:
            raise InvalidMessageError(
                "There's more than one attachment to this message. It cannot "
                "be indexed automatically."
            )

        self.attachment = attachments[0]

    def __bool__(self):
        return bool(self.attachment)

    def check_subject(self):
        if self.subject is None:
            raise InvalidMessageError("Message does not have a subject")
        if not Sender.SAFE_REGEX.match(self.subject):
            raise InvalidMessageError("Message subject is unsafe: {}".format(
                self.subject))

    def check_body(self):
        if self.SECRET not in self.body:
            raise InvalidMessageError("The secret wasn't in the body")

    def _set_time(self, message):
        self.time = datetime.datetime.now()
        message_time = message.get("Date")
        if message_time:
            try:
                self.time = parser.parse(message_time)
            except (ValueError, AttributeError):
                pass  # We assume that "now" is ok

    @property
    def file_name(self):
        return "{}.{}".format(self.subject, self.attachment.suffix)


class Attachment(object):

    SAFE_SUFFIX_REGEX = re.compile(
        r"^(application/(pdf))|(image/(png|jpeg|gif|tiff))$")

    def __init__(self, data, content_type):

        self.content_type = content_type
        self.data = data
        self.suffix = None

        m = self.SAFE_SUFFIX_REGEX.match(self.content_type)
        if not m:
            raise MailFetcherError(
                "Not-awesome file type: {}".format(self.content_type))
        self.suffix = m.group(2) or m.group(4)

    def read(self):
        return self.data


class MailFetcher(object):

    def __init__(self, verbosity=1):

        self._connection = None
        self._host = settings.MAIL_CONSUMPTION["HOST"]
        self._port = settings.MAIL_CONSUMPTION["PORT"]
        self._username = settings.MAIL_CONSUMPTION["USERNAME"]
        self._password = settings.MAIL_CONSUMPTION["PASSWORD"]
        self._inbox = settings.MAIL_CONSUMPTION["INBOX"]

        self._enabled = bool(self._host)

        self.last_checked = datetime.datetime.now()
        self.verbosity = verbosity

    def pull(self):
        """
        Fetch all available mail at the target address and store it locally in
        the consumption directory so that the file consumer can pick it up and
        do its thing.
        """

        if self._enabled:

            Log.info("Checking mail", Log.COMPONENT_MAIL)

            for message in self._get_messages():

                Log.debug(
                    'Storing email: "{}"'.format(message.subject),
                    Log.COMPONENT_MAIL
                )

                t = int(time.mktime(message.time.timetuple()))
                file_name = os.path.join(Consumer.CONSUME, message.file_name)
                with open(file_name, "wb") as f:
                    f.write(message.attachment.data)
                    os.utime(file_name, times=(t, t))

        self.last_checked = datetime.datetime.now()

    def _get_messages(self):

        r = []
        try:

            self._connect()
            self._login()

            for message in self._fetch():
                if message:
                    r.append(message)

            self._connection.expunge()
            self._connection.close()
            self._connection.logout()

        except Exception as e:
            Log.error(e, Log.COMPONENT_MAIL)

        return r

    def _connect(self):
        self._connection = imaplib.IMAP4_SSL(self._host, self._port)

    def _login(self):

        login = self._connection.login(self._username, self._password)
        if not login[0] == "OK":
            raise MailFetcherError("Can't log into mail: {}".format(login[1]))

        inbox = self._connection.select("INBOX")
        if not inbox[0] == "OK":
            raise MailFetcherError("Can't find the inbox: {}".format(inbox[1]))

    def _fetch(self):

        for num in self._connection.search(None, "ALL")[1][0].split():

            __, data = self._connection.fetch(num, "(RFC822)")

            message = None
            try:
                message = Message(data[0][1], self.verbosity)
            except InvalidMessageError as e:
                Log.error(e, Log.COMPONENT_MAIL)
            else:
                self._connection.store(num, "+FLAGS", "\\Deleted")

            if message:
                yield message
