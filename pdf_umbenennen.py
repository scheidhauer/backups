import os
import glob
import re
from google import genai
from pypdf import PdfReader
# Mac-spezifische Bibliotheken für OCR
import Vision
import Quartz
from Cocoa import NSURL
from Foundation import NSDictionary

#
# Starten mit: python3 ../pdf_umbenennen.py
#
# 1. KONFIGURATION
# Versuche .env Datei zu laden (optional, falls python-dotenv installiert ist)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_KEY = os.getenv("GEMINI_API_KEY")

# GEÄNDERT: Nutzt jetzt dynamisch den aktuellen Ordner
ORDNER_PFAD = os.getcwd()

# Sicherheits-Check: Falls die Variable nicht gesetzt ist, bricht das Skript ab
if not API_KEY:
    raise ValueError(
        "Fehler: Die Umgebungsvariable 'GEMINI_API_KEY' wurde nicht gefunden!\n"
        "Bitte erstelle eine '.env' Datei oder setze sie im Terminal mit: export GEMINI_API_KEY='dein_schlüssel'"
    )

client = genai.Client(api_key=API_KEY)

def mac_ocr(image_path):
    """Nutzt die native macOS Texterkennung (Live Text)"""
    input_url = NSURL.fileURLWithPath_(image_path)
    request_handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(input_url, None)
    
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    
    success, error = request_handler.performRequests_error_([request], None)
    if not success:
        return ""
        
    results = request.results()
    text = ""
    for result in results:
        candidates = result.topCandidates_(1)
        if candidates:
            text += candidates[0].string() + "\n"
    return text

def extrahiere_text(pdf_pfad):
    """Versucht erst digitalen Text zu lesen, falls leer -> Mac OCR"""
    reader = PdfReader(pdf_pfad)
    text = ""
    if reader.pages:
        text = reader.pages[0].extract_text() or ""
    
    if not text.strip():
        from pdf2image import convert_from_path
        seiten = convert_from_path(pdf_pfad, first_page=1, last_page=1)
        if seiten:
            temp_img = "temp_page.png"
            seiten[0].save(temp_img, "PNG")
            text = mac_ocr(temp_img)
            os.remove(temp_img)
            
    return text

def generiere_dateiname(text_inhalt):
    """Schickt den Text an Gemini für den Namensvorschlag"""
    prompt = f"""
    Analysiere den folgenden Text aus einem gescannten Dokument. 
    Erstelle einen sinnvollen, kurzen und prägnanten Dateinamen für eine PDF.
    Nutze STRENG das Format: JJJJ-MM-TT_Absender_Thema
    Wenn kein Datum erkennbar ist, nutze 2026-00-00.
    Antworte NUR mit dem reinen Dateinamen (inklusive .pdf am Ende), ohne Formatierung, ohne Markdown, ohne Anführungszeichen.
    
    Text:
    {text_inhalt[:2000]}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text.strip()

def main():
    # Sucht alle PDFs, die mit '202' beginnen
    such_muster = os.path.join(ORDNER_PFAD, "202*.pdf")
    pdf_dateien = glob.glob(such_muster)
    
    # Regex für das Scan-Format: JJJJMMTT_HHMMSS.pdf (z.B. 20260424_083623.pdf)
    scan_muster = re.compile(r"^\d{8}_\d{6}\.pdf$")

    print(f"Aktueller Ordner: {ORDNER_PFAD}")
    
    # Filtere Dateien: Nur die, die exakt dem Scan-Muster entsprechen
    zu_verarbeiten = [f for f in pdf_dateien if scan_muster.match(os.path.basename(f))]

    print(f"{len(zu_verarbeiten)} rohe Scan-PDFs gefunden. Starte Verarbeitung...")

    for pfad in zu_verarbeiten:
        try:
            print(f"\nVerarbeite: {os.path.basename(pfad)}...")
            text = extrahiere_text(pfad)
            
            if not text.strip():
                print("Kein Text im Dokument gefunden (auch nicht per OCR). Überspringe.")
                continue
                
            neuer_name = generiere_dateiname(text)
            neuer_name = "".join(c for c in neuer_name if c.isalnum() or c in ".-_")
            
            neuer_pfad = os.path.join(ORDNER_PFAD, neuer_name)
            
            os.rename(pfad, neuer_pfad)
            print(f"Erfolgreich umbenannt in: {neuer_name}")
            
        except Exception as e:
            print(f"Fehler bei {os.path.basename(pfad)}: {e}")

if __name__ == "__main__":
    main()
