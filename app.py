from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageChops
import re
import io
import base64
import numpy as np

app = Flask(__name__)
# CORS allow karta hai aapki website ko is Python server se baat karne ke liye
CORS(app) 

def transparent_white_color(img_pil):
    """Converts white-ish background to transparent (Used for Logo & Ashok Chakra)"""
    img = img_pil.convert("RGBA")
    datas = img.getdata()
    newData = []
    for item in datas:
        # If r > 180, g > 180, b > 180 make transparent
        if item[0] > 180 and item[1] > 180 and item[2] > 180:
            newData.append((255, 255, 255, 0))
        else:
            newData.append(item)
    img.putdata(newData)
    return img

def process_card(src_img, scale, is_front, mobile_no, aadhaar_no, vid_no):
    finalW, finalH = 1016, 638
    
    # Create clean white card base
    final_card = Image.new("RGB", (finalW, finalH), "white")
    
    # Erase Header and Footer (white out)
    draw_src = ImageDraw.Draw(src_img)
    draw_src.rectangle([0, 0, src_img.width, 11 * scale], fill="white")
    draw_src.rectangle([0, src_img.height - (7 * scale), src_img.width, src_img.height], fill="white")
    
    # Multiply Blend logic (Darkening base text)
    bg_resized = src_img.resize((finalW, finalH), Image.Resampling.LANCZOS)
    final_card = ImageChops.multiply(final_card, bg_resized)
    
    # Darkness booster boxes (Python overlay)
    dark_overlay = Image.new("RGB", (finalW, finalH), "white")
    dark_draw = ImageDraw.Draw(dark_overlay)
    
    if is_front:
        dark_draw.rectangle([310, 200, finalW, finalH - 170], fill=(220, 220, 220)) 
        dark_draw.rectangle([320, 140, finalW - 500 + 320, 140 + 170], fill=(220, 220, 220))
        dark_draw.rectangle([180, 10, finalW - 415 + 180, finalH - 510 + 10], fill=(220, 220, 220))
    else:
        # BACK SIDE: Darkness extended downwards
        dark_draw.rectangle([15, 150, finalW - 420 + 15, finalH - 150 + 150], fill=(220, 220, 220))
        dark_draw.rectangle([180, 10, finalW - 415 + 180, finalH - 510 + 10], fill=(220, 220, 220))
        
    final_card = ImageChops.multiply(final_card, dark_overlay)

    # =========================================================
    #  AADHAAR LOGO (Transparent, Zoom, Shift)
    # =========================================================
    lX, lY, lW, lH = 805, 20, 200, 110
    logo_crop = final_card.crop((lX, lY, lX+lW, lY+lH))
    logo_trans = transparent_white_color(logo_crop)
    
    # Whitewash original logo area
    ImageDraw.Draw(final_card).rectangle([lX, lY, lX+lW, lY+lH], fill="white")
    
    if is_front:
        lZoom, shiftLeft, heightMult = 1.45, finalW * 0.04, 1.08
        shiftUpAmount = 0
    else:
        lZoom, shiftLeft, heightMult = 1.30, finalW * 0.02, 1.05
        shiftUpAmount = finalH * 0.03
        
    lNewW = int(lW * lZoom)
    lNewH = int((lH * lZoom) * heightMult)
    lNewX = int((lX - ((lNewW - lW) / 2)) - shiftLeft)
    lNewY = int((lY - ((lNewH - lH) / 2)) - shiftUpAmount)
    
    logo_trans = logo_trans.resize((lNewW, lNewH), Image.Resampling.LANCZOS)
    final_card.paste(logo_trans, (lNewX, lNewY), logo_trans) 

    # =========================================================
    # ASHOK CHAKRA (Transparent, Zoom, Shift)
    # =========================================================
    aX, aY, aW, aH = (30 if is_front else 10), 20, 130, 110
    ashok_crop = final_card.crop((aX, aY, aX+aW, aY+aH))
    ashok_trans = transparent_white_color(ashok_crop)
    
    ImageDraw.Draw(final_card).rectangle([aX, aY, aX+aW, aY+aH], fill="white")
    
    aZoom = 1.25
    aShiftRight = finalW * 0.04 if is_front else finalW * 0.02
    aShiftUp = 0 if is_front else finalH * 0.01
    
    aNewW, aNewH = int(aW * aZoom), int(aH * aZoom)
    aNewX = int((30 - ((aNewW - aW) / 2)) + aShiftRight)
    aNewY = int((aY - ((aNewH - aH) / 2)) - aShiftUp)
    
    ashok_trans = ashok_trans.resize((aNewW, aNewH), Image.Resampling.LANCZOS)
    final_card.paste(ashok_trans, (aNewX, aNewY), ashok_trans)

    # =========================================================
    # FRONT SPECIFIC LOGIC (Photo Brightness, Text Replacements)
    # =========================================================
    draw = ImageDraw.Draw(final_card)
    try:
        # Standard Font (Fallback to default if arial is missing)
        font_vid = ImageFont.truetype("arialbd.ttf", 21)
        font_aadhaar = ImageFont.truetype("arialbd.ttf", 44)
        font_mob = ImageFont.truetype("arialbd.ttf", 36)
    except IOError:
        font_vid = font_aadhaar = font_mob = ImageFont.load_default()

    if is_front:
        # Text Zoomer
        tX, tY, tW, tH = 320, 150, 500, 150
        text_crop = final_card.crop((tX, tY, tX+tW, tY+tH))
        draw.rectangle([tX, tY, tX+tW, tY+tH], fill="white")
        
        tZoom, tShiftRight = 1.25, finalW * 0.06
        tNewW, tNewH = int(tW * tZoom), int(tH * tZoom)
        tNewX = int(tX - ((tNewW - tW) / 2) + tShiftRight)
        tNewY = int(tY - ((tNewH - tH) / 2))
        
        text_crop = text_crop.resize((tNewW, tNewH), Image.Resampling.LANCZOS)
        final_card.paste(text_crop, (tNewX, tNewY))
        
        # Replace Aadhaar Number Logic (Centered)
        draw.rectangle([300, 530, finalW - 33, 530 + 45], fill="white")
        centerOfCard = finalW / 2
        
        if vid_no:
            draw.text((centerOfCard, 568), f"VID : {vid_no}", fill="black", font=font_vid, anchor="ms")
        if aadhaar_no:
            draw.text((centerOfCard, 542), aadhaar_no, fill="black", font=font_aadhaar, anchor="ms")
            
        # 🔥 PHOTO ZOOMER & BRIGHTNESS LOGIC (30% Extra Light) 🔥
        pX, pY, pW, pH = 85, 160, 212, 230
        photo_crop = final_card.crop((pX, pY, pX+pW, pY+pH))
        
        enhancer = ImageEnhance.Brightness(photo_crop)
        photo_crop = enhancer.enhance(1.3) # 30% Brightness increase BEFORE paste
        
        draw.rectangle([pX, pY, pX+pW, pY+pH], fill="white")
        
        pZoom = 1.20
        pNewW, pNewH = int(pW * pZoom), int(pH * pZoom)
        pNewX = int(pX - ((pNewW - pW) / 1.50))
        pNewY = int(pY - ((pNewH - pH) / 16))
        
        photo_crop = photo_crop.resize((pNewW, pNewH), Image.Resampling.LANCZOS)
        final_card.paste(photo_crop, (pNewX, pNewY))
        draw.rectangle([pNewX, pNewY, pNewX+pNewW, pNewY+pNewH], outline="black", width=3)
        
        # RED BOX RESIZER
        boxX, boxY = 333, 320
        cutH, boxW = 190, finalW - boxX
        pasteH, pasteW = 120, int(boxW * 0.93)
        
        box_crop = final_card.crop((boxX, boxY, boxX+boxW, boxY+cutH))
        draw.rectangle([boxX, boxY, boxX+boxW, boxY+cutH], fill="white")
        
        newY = boxY + 68
        box_crop = box_crop.resize((pasteW, pasteH), Image.Resampling.LANCZOS)
        final_card.paste(box_crop, (boxX, newY))
        
        # Mobile Number Print
        if mobile_no and len(mobile_no) == 10:
            draw.text((337, 366), f"Mob: {mobile_no}", fill="black", font=font_mob)

    # Border around card
    draw.rectangle([0, 0, finalW-1, finalH-1], outline="#333", width=1)
    
    return final_card

def pil_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

@app.route('/process_aadhaar', methods=['POST'])
def process_aadhaar():
    if 'pdf_file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    pdf_file = request.files['pdf_file']
    password = request.form.get('password', '')
    auto_mobile = request.form.get('autoMobile', 'no') == 'yes'
    
    try:
        # Load PDF
        pdf_bytes = pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if doc.needs_pass:
            if not doc.authenticate(password):
                return jsonify({"error": "Incorrect Password"}), 401
                
        page = doc[0]
        
        # 1. Text Extraction
        full_text = page.get_text()
        foundMobile = ""
        foundAadhaar = ""
        foundVID = ""
        
        if auto_mobile:
            mob_match = re.search(r'[6-9][0-9]{9}', full_text)
            if mob_match: foundMobile = mob_match.group()
            
        aadhaar_match = re.search(r'[0-9]{4}\s[0-9]{4}\s[0-9]{4}', full_text)
        if aadhaar_match: foundAadhaar = aadhaar_match.group()
        
        vid_match = re.search(r'[0-9]{4}\s[0-9]{4}\s[0-9]{4}\s[0-9]{4}', full_text)
        if vid_match: foundVID = vid_match.group()

        # 2. Render Page to Image (Scale = 3)
        scale = 3
        zoom_matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=zoom_matrix)
        pdf_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        pdfH = pdf_img.height
        cropY = int(pdfH - (228 * scale))
        cropH = int(174 * scale)
        cropW = int(246 * scale)
        frontX = int(52 * scale)
        backX = int(318 * scale)
        
        # Crop Front & Back
        front_src = pdf_img.crop((frontX, cropY, frontX+cropW, cropY+cropH))
        back_src = pdf_img.crop((backX, cropY, backX+cropW, cropY+cropH))
        
        # Process Images
        front_final = process_card(front_src, scale, True, foundMobile, foundAadhaar, foundVID)
        back_final = process_card(back_src, scale, False, "", "", "")
        
        return jsonify({
            "front_image": pil_to_base64(front_final),
            "back_image": pil_to_base64(back_final)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
