"""Explicitly synthetic edge-case images, made in memory for regression tests."""
import io
from PIL import Image, ImageFilter
from medbill.samples import bill_pdf, raster, SAMPLES


def png(image):
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def fixtures():
    # Fabricated codes/charges are test inputs, never reference data.
    unknown = {'id':'unknown', 'title':'SYNTHETIC UNKNOWN CODE TEST', 'layout':'standard',
               'rows':[['07/15/2026','99999','Unverified sample service','1','75.00']]}
    old_date = {'id':'old_date', 'title':'SYNTHETIC UNSUPPORTED DATE TEST', 'layout':'standard',
                'rows':[['01/15/2025','99213','Office visit','1','250.00']]}
    return {
        'blank': png(Image.new('RGB',(1800,2200),'white')),
        'severely_blurred': png(raster(bill_pdf(SAMPLES[0]),200/72).filter(ImageFilter.GaussianBlur(12))),
        'unknown_code': png(raster(bill_pdf(unknown))),
        'unsupported_date': png(raster(bill_pdf(old_date))),
    }
