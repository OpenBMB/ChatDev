import cv2
import numpy as np
from PIL import Image

def remove_background(image):
    
    image = np.array(image)
    
    mask = np.zeros(image.shape[:2], np.uint8)
    
    bgdModel = np.zeros((1, 65), np.float64)

    fgdModel = np.zeros((1, 65), np.float64)

    rect = (50, 50, image.shape[1] - 50, image.shape[0] - 50)

    cv2.grabCut(image, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)

    fg_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')

    result = image * fg_mask[:, :, np.newaxis]

    result = Image.fromarray(result)

    return result
