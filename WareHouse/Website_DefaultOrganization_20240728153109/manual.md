# ChatDev Landing Page

## Introduction

The ChatDev Landing Page is a Python-based web application that allows you to create a landing page with two images from the image.startr.cloud API service. This manual will guide you through the installation process and explain how to use the software effectively.

## Installation

To install the ChatDev Landing Page, follow these steps:

1. Make sure you have Python installed on your system. You can download Python from the official website: [https://www.python.org/downloads/](https://www.python.org/downloads/)

2. Clone the ChatDev Landing Page repository from GitHub: [https://github.com/your-repo](https://github.com/your-repo)

3. Navigate to the cloned repository in your terminal or command prompt.

4. Create a virtual environment to isolate the project dependencies. Run the following command:

   ```
   python -m venv venv
   ```

5. Activate the virtual environment. Run the following command:

   - For Windows:

     ```
     venv\Scripts\activate
     ```

   - For macOS/Linux:

     ```
     source venv/bin/activate
     ```

6. Install the required dependencies. Run the following command:

   ```
   pip install -r requirements.txt
   ```

7. Run the application. Execute the following command:

   ```
   python main.py
   ```

8. The ChatDev Landing Page should now be running on your local machine. Open your web browser and navigate to [http://localhost:5000](http://localhost:5000) to access the landing page.

## Usage

Once the ChatDev Landing Page is running, you can use it to create a landing page with the blue and purple images from the image.startr.cloud API service.

The landing page will display the images in a canvas with a size of 1000x400 pixels. The blue image will be displayed at the top-left corner, and the purple image will be displayed at the top-right corner.

To customize the landing page with different images, you can modify the URLs in the `main.py` file. Update the `load_and_display_image` function calls with the desired image URLs.

```python
# Load and display blue image
self.load_and_display_image("https://image.startr.cloud/1000x400/blue_", 0, 0)

# Load and display purple image
self.load_and_display_image("https://image.startr.cloud/1000x400/purple_", 500, 0)
```

Save the changes and restart the application to see the updated landing page with the new images.

## Conclusion

Congratulations! You have successfully installed and used the ChatDev Landing Page software. You can now create landing pages with the blue and purple images from the image.startr.cloud API service. Enjoy exploring the possibilities of creating visually appealing landing pages with ease. If you have any further questions or need assistance, please don't hesitate to reach out to our support team.