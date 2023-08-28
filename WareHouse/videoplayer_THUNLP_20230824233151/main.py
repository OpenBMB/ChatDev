'''
This is the main file of the video player application.
'''
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from video_player import VideoPlayer
class VideoPlayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Player")
        self.video_player = VideoPlayer()
        self.open_button = tk.Button(self.root, text="Open", command=self.open_file)
        self.open_button.pack()
        self.play_button = tk.Button(self.root, text="Play", command=self.play_video)
        self.play_button.pack()
    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4")])
        if file_path:
            self.video_player.load_video(file_path)
            messagebox.showinfo("Success", "Video loaded successfully!")
    def play_video(self):
        if self.video_player.is_loaded():
            self.video_player.play()
        else:
            messagebox.showerror("Error", "No video loaded!")
if __name__ == "__main__":
    root = tk.Tk()
    app = VideoPlayerApp(root)
    root.mainloop()