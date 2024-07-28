# MusicPlayer

A user-friendly application to play local mp3 files with essential functionalities and metadata display.

## Quick Install

Before running the application, ensure you have the following Python libraries installed:

- tkinter
- pygame
- mutagen

You can install these libraries using pip:

```
pip install python-tk pygame mutagen
```

## 🤔 What is this?

MusicPlayer is a software application that enables users to play local mp3 files with an intuitive and user-friendly graphical user interface (GUI). The software is designed to run on various operating systems and provides essential functionalities such as play, pause, stop, and volume control. It supports the playback of mp3 files stored locally on the user's device. The user interface allows users to easily browse and select mp3 files from their local directories. Additionally, the software displays relevant metadata information for each mp3 file, such as title, artist, album, and duration. The application provides a visually appealing and responsive interface, ensuring smooth playback without any glitches or delays. The software also includes error handling mechanisms to gracefully handle any exceptions or invalid file formats encountered during playback.

## 📖 How to use it?

1. Run the `main.py` file to start the application.

2. The application will open a directory selection dialog. Navigate to the directory containing your mp3 files and select it.

3. The application will load all mp3 files from the selected directory into the playlist.

4. Select a song from the playlist and use the control panel to play, pause, stop, or adjust the volume of the playback.

5. The application will display the title, artist, and duration of the currently playing song.

6. In case of an error (e.g., if the selected file is not an mp3 file), the application will display an error message.

## 📚 Documentation

Please refer to the comments in the `main.py` file for a detailed explanation of the code. The application uses the tkinter library for the GUI, pygame for playing the music, and mutagen for handling the metadata of mp3 files. The application includes a directory selection dialog, metadata display on the GUI, improved error handling, and a method to unpause the music. It also handles the case where the user selects a non-mp3 file.