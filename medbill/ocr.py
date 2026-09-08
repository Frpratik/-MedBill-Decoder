"""OpenCV preprocessing and actual Tesseract OCR, entirely through memory.

No vision API, PDF text-layer shortcut, temporary image, or uploaded-file cache.
The CLI reads an existing synthetic input and prints JSON to stdout.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageOps
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES, MAX_PIXELS, MAX_PAGES = 20 * 1024 * 1024, 20_000_000, 10


class OCRError(ValueError):
    pass


def tesseract_path():
    override = os.environ.get('TESSERACT_CMD')
    candidates = [override] if override else [shutil.which('tesseract'),
        str(ROOT / '.tools/tesseract/tesseract.exe'), r'C:\Program Files\Tesseract-OCR\tesseract.exe']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise OCRError('Tesseract executable not found. Install Tesseract and English data; set TESSERACT_CMD if needed.')


def rasterize(data):
    if not data or len(data) > MAX_BYTES:
        raise OCRError('Input must be nonempty and no larger than 20 MiB.')
    if data.startswith(b'%PDF-'):
        try:
            document = pdfium.PdfDocument(data)
            try:
                if not 1 <= len(document) <= MAX_PAGES:
                    raise OCRError('PDF must have 1–10 pages.')
                for page in document:
                    try:
                        width, height = page.get_size()
                        if width * height * (300 / 72) ** 2 > MAX_PIXELS:
                            raise OCRError('PDF page exceeds the 20-megapixel limit at 300 DPI.')
                        bitmap = page.render(scale=300 / 72)
                        try:
                            yield bitmap.to_pil().convert('RGB').copy()
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
            finally:
                document.close()
        except pdfium.PdfiumError as error:
            raise OCRError('PDF is damaged, unsupported, or password-protected.') from error
    else:
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in ('PNG','JPEG','TIFF','BMP','WEBP'):
                    raise OCRError('Supported inputs: PDF, PNG, JPEG, TIFF, BMP, WEBP.')
                if getattr(image, 'n_frames', 1) != 1:
                    raise OCRError('Multi-frame images are unsupported; use a multipage PDF.')
                if image.width * image.height > MAX_PIXELS:
                    raise OCRError('Image exceeds the 20-megapixel limit.')
                oriented = ImageOps.exif_transpose(image)
                rgba = oriented.convert('RGBA')
                background = Image.new('RGBA', rgba.size, 'white')
                yield Image.alpha_composite(background, rgba).convert('RGB')
        except (OSError, Image.DecompressionBombError) as error:
            raise OCRError('Image is damaged or unsupported.') from error


def rotate(image, angle, background=255):
    h, w = image.shape[:2]
    transform = cv2.getRotationMatrix2D((w / 2, h / 2), float(angle), 1)
    return cv2.warpAffine(image, transform, (w,h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=background)


def deskew_angle(gray):
    # Projection-profile search: aligned text produces sharper horizontal rows.
    # The returned angle is the measured correction, not a claimed probability.
    small = cv2.resize(gray, (1000, max(1, round(gray.shape[0] * 1000 / gray.shape[1]))))
    binary = cv2.threshold(small,0,255,cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    def score(angle):
        rows = rotate(binary,angle,0).sum(axis=1, dtype=np.float64)
        return float(np.mean(np.diff(rows) ** 2))
    base = score(0)
    if base == 0:
        return 0.0
    coarse = np.arange(-5,5.01,0.5)
    angle = max(coarse, key=score)
    fine = np.arange(max(-5,angle-0.4),min(5,angle+0.4)+0.01,0.1)
    angle = float(max(fine,key=score))
    return round(angle,2) if score(angle) > base * 1.05 else 0.0


def preprocess(image):
    rgb = np.asarray(image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    original_shape = list(gray.shape)
    if gray.shape[1] < 1600:
        scale = min(2.0,1600/gray.shape[1])
        if gray.size * scale * scale <= MAX_PIXELS:
            gray = cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
    sharpness = float(cv2.Laplacian(gray,cv2.CV_64F).var())
    denoised = cv2.medianBlur(gray,3)
    angle = deskew_angle(denoised)
    aligned = rotate(denoised,angle) if angle else denoised
    binary = cv2.adaptiveThreshold(aligned,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,41,15)
    # Remove long table rules; retain the text strokes. This does not infer text.
    ink = 255-binary
    horizontal = cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(80,ink.shape[1]//15)),np.uint8))
    vertical = cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(80,ink.shape[0]//15),1),np.uint8))
    clean = cv2.bitwise_or(binary,cv2.bitwise_or(horizontal,vertical))
    return clean, {'original_shape':original_shape,'processed_shape':list(clean.shape),
                   'deskew_correction_degrees':angle,'laplacian_variance':round(sharpness,2),
                   'method':'median denoise; projection deskew +/-5 degrees; adaptive Gaussian threshold; rule removal'}


def recognize(image, page_number, *, timeout=60):
    ok, png = cv2.imencode('.png',image)
    if not ok:
        raise OCRError('Could not encode preprocessed image.')
    command = [tesseract_path(),'stdin','stdout','-l','eng','--dpi','300','--psm','6','tsv']
    try:
        result = subprocess.run(command,input=png.tobytes(),capture_output=True,timeout=timeout,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    except subprocess.TimeoutExpired as error:
        raise OCRError('Tesseract exceeded the per-page time limit.') from error
    if result.returncode:
        raise OCRError('Tesseract failed. Verify the executable and eng.traineddata installation.')
    groups = {}
    for row in csv.DictReader(io.StringIO(result.stdout.decode('utf-8')),delimiter='\t',quoting=csv.QUOTE_NONE):
        if row['level'] != '5' or not row['text'].strip():
            continue
        word = {key:int(row[key]) for key in ('left','top','width','height')}
        word.update(text=row['text'],confidence=float(row['conf']))
        key = (row['block_num'],row['par_num'],row['line_num'])
        groups.setdefault(key,[]).append(word)
    lines=[]
    for words in groups.values():
        words.sort(key=lambda w:w['left'])
        lines.append({'page':page_number,'text':' '.join(w['text'] for w in words), 'words':words,
                      'top':min(w['top'] for w in words),
                      'confidence':round(sum(w['confidence'] for w in words)/len(words),2)})
    return sorted(lines,key=lambda line:line['top'])


def extract(data):
    from medbill.parser import parse_lines
    pages, all_lines = [], []
    for number,image in enumerate(rasterize(data),1):
        clean, metadata = preprocess(image)
        lines = recognize(clean,number)
        all_lines.extend(lines)
        pages.append({'page':number,**metadata,'text':'\n'.join(line['text'] for line in lines),
                      'lines':lines})
    result = parse_lines(all_lines)
    result.update(pages=pages,engine='Tesseract',language='eng',processing='local; in-memory; no LLM')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path)
    p.add_argument('--synthetic',action='store_true',required=True,help='Confirm that this is synthetic/public sample data, never PHI.')
    args=p.parse_args()
    try:
        if args.input.stat().st_size > MAX_BYTES:
            raise OCRError('Input exceeds 20 MiB.')
        print(json.dumps(extract(args.input.read_bytes()),indent=2))
    except (OCRError,OSError) as error:
        p.error(str(error))


if __name__ == '__main__':
    main()
