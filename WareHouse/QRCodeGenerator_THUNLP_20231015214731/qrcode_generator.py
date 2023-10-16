'''
This file contains the QRCodeGenerator class responsible for generating QR codes.
'''
import qrcode
class QRCodeGenerator:
    def __init__(self, data):
        self.data = data
    def generate_qr_code(self, file_path):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(self.data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill="black", back_color="white")
        qr_img.save(file_path)