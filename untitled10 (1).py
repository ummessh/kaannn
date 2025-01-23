# -*- coding: utf-8 -*-
"""Untitled10.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1ty7cKtoyWlRA0XU8OZryeflPp9HEWjHd
"""

pip install pytesseract Pillow

import streamlit as st
import sys
import subprocess

# Install dependencies
def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# List of packages to install
packages = [
    'streamlit',
    'pytesseract',
    'pillow',
    'opencv-python-headless'
]

for package in packages:
    install(package)

import pytesseract
from PIL import Image
import os
import cv2
import numpy as np
import sqlite3
from typing import Dict, Optional
import logging

# Language codes
LANGUAGE_CODES = {
    'english': 'eng',
    'hindi': 'hin',
    'marathi': 'mar',
    'punjabi': 'pan',
    'gujarati': 'guj'
}

class Database:
    def __init__(self, db_name: str = 'ocr_results.db'):
        self.db_name = db_name
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('DROP TABLE IF EXISTS ocr_results')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ocr_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                detected_language TEXT NOT NULL,
                confidence FLOAT,
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL
            )
        ''')
        self.conn.commit()

    def save_result(self, image_path: str, text: str, language: str, confidence: float, status: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO ocr_results (image_path, extracted_text, detected_language, confidence, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (image_path, text, language, confidence, status))
        self.conn.commit()
        return cursor.lastrowid

class SmartOCR:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.db = Database()

    def convert_to_grayscale(self, image_path: str) -> np.ndarray:
        img = cv2.imread(image_path)
        gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray_image, (3, 3), 0)

    def apply_thresholding(self, gray_image: np.ndarray) -> np.ndarray:
        return cv2.adaptiveThreshold(
            gray_image,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )

    def preprocess_image(self, image_path: str, apply_threshold: bool = False) -> Image.Image:
        gray_image = self.convert_to_grayscale(image_path)

        if apply_threshold:
            gray_image = self.apply_thresholding(gray_image)

        return Image.fromarray(gray_image)

    def detect_language(self, image: Image.Image) -> tuple:
        try:
            best_confidence = 0
            detected_lang = 'english'

            for lang_name, lang_code in LANGUAGE_CODES.items():
                try:
                    data = pytesseract.image_to_data(image, lang=lang_code, output_type=pytesseract.Output.DICT)
                    conf_scores = [float(x) for x in data['conf'] if x != '-1']
                    if conf_scores:
                        avg_conf = sum(conf_scores) / len(conf_scores)
                        if avg_conf > best_confidence:
                            best_confidence = avg_conf
                            detected_lang = lang_name
                except:
                    continue

            return detected_lang, best_confidence

        except Exception as e:
            self.logger.error(f"Error in language detection: {str(e)}")
            return 'english', 0.0

    def extract_text(self, image_path: str, apply_threshold: bool = False) -> Dict[str, str]:
        try:
            processed_img = self.preprocess_image(image_path, apply_threshold)
            detected_lang, confidence = self.detect_language(processed_img)

            lang_code = LANGUAGE_CODES[detected_lang]
            text = pytesseract.image_to_string(processed_img, lang=lang_code)

            status = 'success' if text.strip() else 'warning'

            result = {
                'status': status,
                'message': f'Text extracted {"successfully" if status=="success" else "with no result"} in {detected_lang}',
                'text': text.strip(),
                'language': detected_lang,
                'confidence': confidence
            }

            # Save to database
            result['id'] = self.db.save_result(
                image_path=image_path,
                text=result['text'],
                language=detected_lang,
                confidence=confidence,
                status=result['status']
            )

            return result

        except Exception as e:
            return {
                'status': 'error',
                'message': f"Error processing image: {str(e)}",
                'text': '',
                'language': 'unknown',
                'confidence': 0.0
            }

def main():
    st.title("📝 Smart OCR Text Extractor")

    # Install Tesseract
    subprocess.check_call(['apt-get', 'update'])
    subprocess.check_call(['apt-get', 'install', '-y', 'tesseract-ocr'])

    # Initialize OCR
    ocr = SmartOCR()

    # File uploader
    uploaded_file = st.file_uploader("Upload an Image", type=["png", "jpg", "jpeg", "bmp"])

    # Thresholding option
    use_threshold = st.checkbox("Apply Advanced Image Processing", value=False)

    if uploaded_file is not None:
        # Create temp directory if not exists
        os.makedirs("temp", exist_ok=True)

        # Save uploaded file
        temp_path = os.path.join("temp", uploaded_file.name)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Display uploaded image
        st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)

        # Extract text
        try:
            result = ocr.extract_text(temp_path, apply_threshold=use_threshold)

            # Display results
            st.subheader("Extraction Results")

            if result['status'] == 'success':
                st.success(result['message'])

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Detected Language", result['language'])
                with col2:
                    st.metric("Confidence", f"{result['confidence']:.2f}%")

                st.text_area("Extracted Text", result['text'], height=200)
            else:
                st.warning(result['message'])

            # Clean up temp file
            os.remove(temp_path)

        except Exception as e:
            st.error(f"Error processing image: {str(e)}")

if __name__ == "__main__":
    main()