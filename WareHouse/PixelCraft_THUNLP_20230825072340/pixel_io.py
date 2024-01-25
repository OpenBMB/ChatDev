'''
Pixel Art I/O
'''
from PIL import Image
def export_pixel_art(pixel_canvas, file_path, file_format):
    image = create_image_from_pixel_canvas(pixel_canvas)
    image.save(file_path, format=file_format)
def create_image_from_pixel_canvas(pixel_canvas):
    width = pixel_canvas.winfo_width()
    height = pixel_canvas.winfo_height()
    pixels = []
    for y in range(0, height, pixel_canvas.pixel_size):
        for x in range(0, width, pixel_canvas.pixel_size):
            pixel_color = pixel_canvas.itemcget(pixel_canvas.find_closest(x, y), "fill")
            pixels.extend([pixel_color] * pixel_canvas.pixel_size)
    image = Image.new("RGB", (width, height), "white")
    image.putdata(pixels)
    return image