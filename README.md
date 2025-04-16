# REcaptchER

An automated solution for solving Google's reCAPTCHA challenges using computer vision and machine learning.

## Overview

This project uses the YOLO (You Only Look Once) object detection model along with Playwright for browser automation to solve image-based reCAPTCHA challenges automatically. The system can identify objects like cars, bicycles, traffic lights, and crosswalks, which are commonly used in reCAPTCHA puzzles.

## Features

- Automated browser interaction using Playwright
- Object detection using YOLOv8
- Support for both grid-based (3x3 or 4x4) and multiple image challenges
- Adaptive mapping of reCAPTCHA targets to COCO dataset classes

## Requirements

- Python 3.8+
- Playwright
- Ultralytics YOLO
- PIL (Pillow)
- Requests

## Installation

1. Clone this repository:
```bash
git clone https://github.com/Gh05t666nero/REcaptchER.git
cd REcaptchER
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install
```

4. Make sure to download the YOLOv8 model weights (the script will attempt to download them automatically if not present).

## Usage

Run the script with:

```bash
python main.py
```

The script will:
1. Open a demo reCAPTCHA page
2. Click the reCAPTCHA checkbox
3. Automatically identify and solve the presented image challenge

## Disclaimer

This project is for educational and research purposes only. Using automated tools to bypass CAPTCHA systems may violate terms of service for some websites. Please use responsibly and ethically.

## License

[MIT License](LICENSE)
