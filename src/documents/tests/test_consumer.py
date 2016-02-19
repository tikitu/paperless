# coding=utf-8
from django.test import TestCase

from ..consumer import Consumer


class TestAttachment(TestCase):

    TAGS = ("tag1", "tag2", "tag3")
    CONSUMER = Consumer()

    def _test_guess_attributes_from_name(self, path, sender, title, tags):
        for suffix in ("pdf", "png", "jpg", "jpeg", "gif"):
            f = path.format(suffix)
            results = self.CONSUMER._guess_attributes_from_name(f)
            self.assertEqual(results[0].name, sender, f)
            self.assertEqual(results[1], title, f)
            self.assertEqual(tuple([t.slug for t in results[2]]), tags, f)
            self.assertEqual(results[3], suffix, f)

    def test_guess_attributes_from_name0(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Title.{}", "Sender", "Title", ())

    def test_guess_attributes_from_name1(self):
        self._test_guess_attributes_from_name(
            "/path/to/Spaced Sender - Title.{}", "Spaced Sender", "Title", ())

    def test_guess_attributes_from_name2(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Spaced Title.{}", "Sender", "Spaced Title", ())

    def test_guess_attributes_from_name3(self):
        self._test_guess_attributes_from_name(
            "/path/to/Dashed-Sender - Title.{}", "Dashed-Sender", "Title", ())

    def test_guess_attributes_from_name4(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Dashed-Title.{}", "Sender", "Dashed-Title", ())

    def test_guess_attributes_from_name5(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Title - tag1,tag2,tag3.{}",
            "Sender",
            "Title",
            self.TAGS
        )

    def test_guess_attributes_from_name6(self):
        self._test_guess_attributes_from_name(
            "/path/to/Spaced Sender - Title - tag1,tag2,tag3.{}",
            "Spaced Sender",
            "Title",
            self.TAGS
        )

    def test_guess_attributes_from_name7(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Spaced Title - tag1,tag2,tag3.{}",
            "Sender",
            "Spaced Title",
            self.TAGS
        )

    def test_guess_attributes_from_name8(self):
        self._test_guess_attributes_from_name(
            "/path/to/Dashed-Sender - Title - tag1,tag2,tag3.{}",
            "Dashed-Sender",
            "Title",
            self.TAGS
        )

    def test_guess_attributes_from_name9(self):
        self._test_guess_attributes_from_name(
            "/path/to/Sender - Dashed-Title - tag1,tag2,tag3.{}",
            "Sender",
            "Dashed-Title",
            self.TAGS
        )

    def test_guess_attributes_from_name10(self):
        self._test_guess_attributes_from_name(
            "/path/to/Σενδερ - Τιτλε - tag1,tag2,tag3.{}",
            "Σενδερ",
            "Τιτλε",
            self.TAGS
        )
class Permutations(TestCase):
    CONSUMER = Consumer()

    valid_senders = ['timmy', 'Dr. McWheelie', 'Dash Gor-don', 'ο Θερμαστής']
    valid_titles = ['title', 'Title w Spaces', 'Title a-dash', 'Τίτλος', '']
    valid_tags = ['tag', 'tig,tag', '-', '0,1,2', '']
    valid_suffixes = ['pdf', 'png', 'jpg', 'jpeg', 'gif']

    def _test_guessed_attributes(
            self, filename, title, suffix, sender=None, tags=None):
        got_sender, got_title, got_tags, got_suffix = \
            self.CONSUMER._guess_attributes_from_name(filename)

        # Required
        self.assertEqual(got_title, title, filename)
        self.assertEqual(got_suffix, suffix, filename)
        # Optional
        if sender is None:
            self.assertEqual(got_sender, sender, filename)
        else:
            self.assertEqual(got_sender.name, sender, filename)
        if tags is None:
            self.assertEqual(got_tags, (), filename)
        else:
            self.assertEqual([t.slug for t in got_tags], tags.split(','),
                             filename)

    def test_just_title(self):
        template = '/path/to/{title}.{suffix}'
        for title in self.valid_titles:
            for suffix in self.valid_suffixes:
                spec = dict(title=title, suffix=suffix)
                filename = template.format(**spec)
                self._test_guessed_attributes(filename, **spec)

    def test_title_and_sender(self):
        template = '/path/to/{sender} - {title}.{suffix}'
        for sender in self.valid_senders:
            for title in self.valid_titles:
                for suffix in self.valid_suffixes:
                    spec = dict(sender=sender, title=title, suffix=suffix)
                    filename = template.format(**spec)
                    self._test_guessed_attributes(filename, **spec)

    def test_title_and_sender_and_tags(self):
        template = '/path/to/{sender} - {title} - {tags}.{suffix}'
        for sender in self.valid_senders:
            for title in self.valid_titles:
                for tags in self.valid_tags:
                    for suffix in self.valid_suffixes:
                        spec = dict(sender=sender, title=title,
                                    tags=tags, suffix=suffix)
                        filename = template.format(**spec)
                        self._test_guessed_attributes(filename, **spec)
