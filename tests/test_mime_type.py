import importlib.util
import unittest


def load_types():
    spec = importlib.util.spec_from_file_location("messages", "entity/messages.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MessageBlockType


class MimeTypeTest(unittest.TestCase):
    def test_an_uppercase_image_type_stays_an_image(self):
        block = load_types()
        self.assertEqual(block.from_mime_type("Image/png"), block.IMAGE)

    def test_a_lowercase_image_type_stays_an_image(self):
        block = load_types()
        self.assertEqual(block.from_mime_type("image/png"), block.IMAGE)

    def test_an_uppercase_audio_type_stays_audio(self):
        block = load_types()
        self.assertEqual(block.from_mime_type("AUDIO/mpeg"), block.AUDIO)

    def test_plain_text_stays_a_file(self):
        block = load_types()
        self.assertEqual(block.from_mime_type("text/plain"), block.FILE)


if __name__ == "__main__":
    unittest.main()
