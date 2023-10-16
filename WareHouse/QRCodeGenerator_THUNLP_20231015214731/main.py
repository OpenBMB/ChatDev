'''
This is the main file that contains the user interface and orchestrates the generation of QR codes.
'''
import tkinter as tk
from tkinter import filedialog, messagebox
import qrcode
class QRCodeGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("QR Code Generator")
        self.data_label = tk.Label(root, text="Enter data or text:")
        self.data_label.pack()
        self.data_entry = tk.Entry(root)
        self.data_entry.pack()
        self.file_label = tk.Label(root, text="Choose file name and format:")
        self.file_label.pack()
        self.file_entry = tk.Entry(root)
        self.file_entry.pack()
        self.file_button = tk.Button(root, text="Choose File", command=self.choose_file)
        self.file_button.pack()
        self.generate_button = tk.Button(root, text="Generate QR Code", command=self.generate_qr_code)
        self.generate_button.pack()
    def choose_file(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png")
        self.file_entry.delete(0, tk.END)
        self.file_entry.insert(0, file_path)
    def generate_qr_code(self):
        data = self.data_entry.get()
        file_path = self.file_entry.get()
        if data and file_path:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(data)
            qr.make(fit=True)
            qr_img = qr.make_image(fill="black", back_color="white")
            qr_img.save(file_path)
            messagebox.showinfo("Success", "QR Code generated and saved successfully!")
        else:
            messagebox.showerror("Error", "Please enter data and choose a file name.")
root = tk.Tk()
app = QRCodeGenerator(root)
root.mainloop()