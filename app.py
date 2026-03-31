from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageChops
import re
import io
import base64
import os
import urllib.request

app = Flask(__name__)
CORS(app) 

# 🔥 FONT DOWNLOADER FOR TIMES NEW ROMAN BOLD 🔥
FONT_PATH = "/tmp/timesbd.ttf" # timesbd.ttf = Times New Roman Bold
if not os.path.exists(FONT_PATH):
    try:
        # Times New Roman Bold ki direct TTF file download karein
        font_url = "https://github.com/mrbvrz/segoe-ui-linux/raw/master/font/timesbd.ttf" 
        urllib.request.urlretrieve(font_url, FONT_PATH)
    except Exception as e:
        print("Times New Roman font download failed:", e)
# =====================================================================
# SMART SCANNER: PDF के अंदर से Photo और QR को ढूँढना
# =====================================================================
def extract_dynamic_assets(doc):
    face_img = None
    qr_img = None
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)
        
        for img_info in image_list:
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            
            w, h = img.size
            aspect_ratio = w / h
            
            # QR Code
            if 0.95 <= aspect_ratio <= 1.05 and w > 100:
                qr_img = img
            # Face
            elif 0.65 <= aspect_ratio <= 0.85 and w > 50:
                face_img = img
                
    return face_img, qr_img

def transparent_white_color(img_pil):
    img = img_pil.convert("RGBA")
    datas = img.getdata()
    newData = []
    for item in datas:
        if item[0] > 180 and item[1] > 180 and item[2] > 180:
            newData.append((255, 255, 255, 0))
        else:
            newData.append(item)
    img.putdata(newData)
    return img

def process_card(src_img, scale, is_front, mobile_no, aadhaar_no, vid_no, face_img, qr_img):
    finalW, finalH = 1016, 638
    
    # 🔥 BACKGROUND FIX: Remove blackish/greyish tint (Make it pure white) 🔥
    enhancer = ImageEnhance.Brightness(src_img)
    src_img = enhancer.enhance(1.2) # Brightness badhai
    enhancer_contrast = ImageEnhance.Contrast(src_img)
    src_img = enhancer_contrast.enhance(1.1) # Contrast badhaya taaki background white ho jaye
    
    final_card = Image.new("RGB", (finalW, finalH), "white")
    
    draw_src = ImageDraw.Draw(src_img)
    draw_src.rectangle([0, 0, src_img.width, 11 * scale], fill="white")
    draw_src.rectangle([0, src_img.height - (7 * scale), src_img.width, src_img.height], fill="white")
    
    bg_resized = src_img.resize((finalW, finalH), Image.Resampling.LANCZOS)
    final_card = ImageChops.multiply(final_card, bg_resized)
    
    # Darkness booster (Thoda sa light kar diya taaki ganda na lage)
    dark_overlay = Image.new("RGB", (finalW, finalH), "white")
    dark_draw = ImageDraw.Draw(dark_overlay)
    if is_front:
        dark_draw.rectangle([310, 200, finalW, finalH - 170], fill=(235, 235, 235)) 
        dark_draw.rectangle([320, 140, finalW - 500 + 320, 140 + 170], fill=(235, 235, 235))
        dark_draw.rectangle([180, 10, finalW - 415 + 180, finalH - 510 + 10], fill=(235, 235, 235))
    else:
        dark_draw.rectangle([15, 150, finalW - 420 + 15, finalH - 150 + 150], fill=(235, 235, 235))
        dark_draw.rectangle([180, 10, finalW - 415 + 180, finalH - 510 + 10], fill=(235, 235, 235))
    final_card = ImageChops.multiply(final_card, dark_overlay)

    # Logos (Emblem & Aadhaar Logo)
    lX, lY, lW, lH = 805, 20, 200, 110
    logo_crop = final_card.crop((lX, lY, lX+lW, lY+lH))
    logo_trans = transparent_white_color(logo_crop)
    ImageDraw.Draw(final_card).rectangle([lX, lY, lX+lW, lY+lH], fill="white")
    
    if is_front:
        lNewW, lNewH = int(lW * 1.45), int((lH * 1.45) * 1.08)
        lNewX, lNewY = int((lX - ((lNewW - lW) / 2)) - (finalW * 0.04)), int((lY - ((lNewH - lH) / 2)))
    else:
        lNewW, lNewH = int(lW * 1.30), int((lH * 1.30) * 1.05)
        lNewX, lNewY = int((lX - ((lNewW - lW) / 2)) - (finalW * 0.02)), int((lY - ((lNewH - lH) / 2)) - (finalH * 0.03))
    
    logo_trans = logo_trans.resize((lNewW, lNewH), Image.Resampling.LANCZOS)
    final_card.paste(logo_trans, (lNewX, lNewY), logo_trans) 

    aX, aY, aW, aH = (30 if is_front else 10), 20, 130, 110
    ashok_crop = final_card.crop((aX, aY, aX+aW, aY+aH))
    ashok_trans = transparent_white_color(ashok_crop)
    ImageDraw.Draw(final_card).rectangle([aX, aY, aX+aW, aY+aH], fill="white")
    
    aNewW, aNewH = int(aW * 1.25), int(aH * 1.25)
    aNewX = int((30 - ((aNewW - aW) / 2)) + (finalW * 0.04 if is_front else finalW * 0.02))
    aNewY = int((aY - ((aNewH - aH) / 2)) - (0 if is_front else finalH * 0.01))
    ashok_trans = ashok_trans.resize((aNewW, aNewH), Image.Resampling.LANCZOS)
    final_card.paste(ashok_trans, (aNewX, aNewY), ashok_trans)

    draw = ImageDraw.Draw(final_card)
    
    # 🔥 FONT LOADING 🔥
    try:
        font_vid = ImageFont.truetype(FONT_PATH, 28)
        font_aadhaar = ImageFont.truetype(FONT_PATH, 45) # Bada Aadhaar Font
        font_mob = ImageFont.truetype(FONT_PATH, 31) # Bada Mobile Font
    except IOError:
        font_vid = font_aadhaar = font_mob = ImageFont.load_default()

    # =========================================================
    # FRONT SIDE FIXES
    # =========================================================
    if is_front:
        # Top Address Text Zoomer
        tX, tY, tW, tH = 320, 150, 500, 150
        text_crop = final_card.crop((tX, tY, tX+tW, tY+tH))
        draw.rectangle([tX, tY, tX+tW, tY+tH], fill="white")
        tNewW, tNewH = int(tW * 1.25), int(tH * 1.25)
        tNewX, tNewY = int(tX - ((tNewW - tW) / 2) + (finalW * 0.06)), int(tY - ((tNewH - tH) / 2))
        final_card.paste(text_crop.resize((tNewW, tNewH), Image.Resampling.LANCZOS), (tNewX, tNewY))
        
     # 🔥 AADHAAR & VID FIX (Perfect placement, clear old text) 🔥
        draw.rectangle([250, 480, finalW - 50, 595], fill="white") # Bada White Box
        centerOfCard = finalW / 2
        
        if aadhaar_no: 
            # छुपे हुए Newlines (\n) को हटाकर सिंगल स्पेस में बदलना
            clean_aadhaar = " ".join(aadhaar_no.split())
            
            text_length = draw.textlength(clean_aadhaar, font=font_aadhaar)
            x_pos = centerOfCard - (text_length / 2)
            draw.text((x_pos, 490), clean_aadhaar, fill="black", font=font_aadhaar)
            
        if vid_no: 
            # छुपे हुए Newlines (\n) को हटाकर सिंगल स्पेस में बदलना
            clean_vid = " ".join(vid_no.split())
            
            vid_text = f"VID : {clean_vid}"
            text_length = draw.textlength(vid_text, font=font_vid)
            x_pos = centerOfCard - (text_length / 2)
            draw.text((x_pos, 555), vid_text, fill="black", font=font_vid)
        # PHOTO PASTE
        pX, pY, pW, pH = 55, 140, 255, 300 
        draw.rectangle([pX-10, pY-10, pX+pW+10, pY+pH+10], fill="white") 
        
        if face_img:
            enhancer = ImageEnhance.Brightness(face_img)
            bright_face = enhancer.enhance(1.3)
            final_card.paste(bright_face.resize((pW, pH), Image.Resampling.LANCZOS), (pX, pY))
            draw.rectangle([pX, pY, pX+pW, pY+pH], outline="black", width=3)
        
        # Red Box Fix
        boxX, boxY, cutH, boxW = 333, 320, 190, finalW - 333
        pasteH, pasteW = 120, int(boxW * 0.93)
        box_crop = final_card.crop((boxX, boxY, boxX+boxW, boxY+cutH))
        draw.rectangle([boxX, boxY, boxX+boxW, boxY+cutH], fill="white")
        final_card.paste(box_crop.resize((pasteW, pasteH), Image.Resampling.LANCZOS), (boxX, boxY + 68))
        
        # Mobile Number Print Fix
        if mobile_no and len(mobile_no) == 10:
            draw.rectangle([330, 340, 600, 390], fill="white") # Clear space for mobile
            draw.text((337, 345), f"Mob: {mobile_no}", fill="black", font=font_mob)

    # =========================================================
    # BACK SIDE FIXES
    # =========================================================
    if not is_front:
        # 🔥 QR CODE FIX (Remove border by cropping) 🔥
        qX, qY, qW, qH = 650, 150, 330, 330 
        draw.rectangle([qX-20, qY-20, qX+qW+20, qY+qH+20], fill="white") 
        
        if qr_img:
            # Crop 4 pixels from edges to remove black lines
            qw_orig, qh_orig = qr_img.size
            qr_cropped = qr_img.crop((4, 4, qw_orig-4, qh_orig-4))
            
            resized_qr = qr_cropped.resize((qW, qH), Image.Resampling.NEAREST) 
            final_card.paste(resized_qr, (qX, qY))

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
        pdf_bytes = pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if doc.needs_pass:
            if not doc.authenticate(password):
                return jsonify({"error": "Incorrect Password"}), 401
                
        page = doc[0]
        
        face_img, qr_img = extract_dynamic_assets(doc)
        
        full_text = page.get_text()
        foundMobile, foundAadhaar, foundVID = "", "", ""
        
        if auto_mobile:
            mob_match = re.search(r'[6-9][0-9]{9}', full_text)
            if mob_match: foundMobile = mob_match.group()
            
        aadhaar_match = re.search(r'[0-9]{4}\s[0-9]{4}\s[0-9]{4}', full_text)
        if aadhaar_match: foundAadhaar = aadhaar_match.group()
        
        vid_match = re.search(r'[0-9]{4}\s[0-9]{4}\s[0-9]{4}\s[0-9]{4}', full_text)
        if vid_match: foundVID = vid_match.group()

        scale = 3
        zoom_matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=zoom_matrix)
        pdf_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        pdfH = pdf_img.height
        cropY, cropH, cropW = int(pdfH - (228 * scale)), int(174 * scale), int(246 * scale)
        
        front_src = pdf_img.crop((int(52 * scale), cropY, int(52 * scale)+cropW, cropY+cropH))
        back_src = pdf_img.crop((int(318 * scale), cropY, int(318 * scale)+cropW, cropY+cropH))
        
        front_final = process_card(front_src, scale, True, foundMobile, foundAadhaar, foundVID, face_img, qr_img)
        back_final = process_card(back_src, scale, False, "", "", "", face_img, qr_img)
        
        return jsonify({
            "front_image": pil_to_base64(front_final),
            "back_image": pil_to_base64(back_final)
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
