# Online HTML World Clock User Manual

## Introduction

The Online HTML World Clock is a web-based application that displays the current time in different cities around the world. It provides a simple and convenient way to keep track of time in multiple time zones.

## Installation

To use the Online HTML World Clock, you need to follow these steps to set up the environment and install the necessary dependencies:

1. Install Python: Make sure you have Python installed on your system. You can download the latest version of Python from the official website: [https://www.python.org/downloads/](https://www.python.org/downloads/)

2. Clone the repository: Download the source code of the Online HTML World Clock from the repository. You can use Git to clone the repository or download it as a ZIP file and extract it to a local directory.

3. Install dependencies: Open a terminal or command prompt and navigate to the directory where you cloned or extracted the source code. Run the following command to install the required dependencies:

   ```
   pip install -r requirements.txt
   ```

   This will install the `pytz` library, which is used for time zone conversions.

## Usage

Once you have installed the dependencies, you can run the Online HTML World Clock application by following these steps:

1. Open a terminal or command prompt and navigate to the directory where you cloned or extracted the source code.

2. Run the following command to start the application:

   ```
   python main.py
   ```

3. The application window will open, displaying the current time in different cities around the world. The cities and their corresponding time zones are:

   - New York: America/New_York
   - London: Europe/London
   - Tokyo: Asia/Tokyo
   - Sydney: Australia/Sydney

   The time will be updated every second.

4. You can resize the application window or move it around on your screen for better visibility.

## Customization

If you want to add or remove cities from the Online HTML World Clock, you can modify the `timezones` dictionary in the `main.py` file. Each city should be mapped to its corresponding time zone identifier.

For example, to add a city named "Paris" with the time zone "Europe/Paris", you can modify the `timezones` dictionary as follows:

```python
timezones = {
    "New York": "America/New_York",
    "London": "Europe/London",
    "Tokyo": "Asia/Tokyo",
    "Sydney": "Australia/Sydney",
    "Paris": "Europe/Paris"
}
```

Save the changes and restart the application for the modifications to take effect.

## Conclusion

The Online HTML World Clock provides a convenient way to keep track of time in different cities around the world. By following the installation and usage instructions in this user manual, you can easily set up and use the application to stay informed about the current time in various time zones.