'''
This is the main file of the e-book reader application.
'''
from ebook_reader import EbookReader
def main():
    # Create an instance of the EbookReader
    reader = EbookReader()
    # Start the application
    reader.start()
if __name__ == "__main__":
    main()