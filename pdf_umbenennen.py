import os
import glob
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
API_KEY = "cccc"

# GEÄNDERT: Nutzt jetzt dynamisch den aktuellen Ordner
ORDNER_PFAD = os.getcwd()

# Sicherheits-Check: Falls die Variable nicht gesetzt ist, bricht das Skript ab
if not API_KEY:
    raise ValueError(
        "Fehler: Die Umgebungsvariable 'GEMINI_API_KEY' wurde nicht gefunden!\n"
        "Bitte setze sie im Terminal mit: export GEMINI_API_KEY='dein_schlüssel'"
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
    such_muster = os.path.join(ORDNER_PFAD, "202*.pdf")
    pdf_dateien = glob.glob(such_muster)
    
    print(f"Aktueller Ordner: {ORDNER_PFAD}")
    print(f"{len(pdf_dateien)} passende PDFs gefunden (beginnend mit '202'). Starte Verarbeitung...")

    for pfad in pdf_dateien:
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
