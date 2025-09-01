from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

def image_to_centered_pdf(image_path, output_pdf_path, margin_mm=20):
    margin = margin_mm * 2.83465

    image = Image.open(image_path)
    img_width, img_height = image.size

    a4_width, a4_height = A4

    max_width = a4_width - 2 * margin
    max_height = a4_height - 2 * margin

    ratio = min(max_width / img_width, max_height / img_height, 1)
    new_width = img_width * ratio
    new_height = img_height * ratio

    x = (a4_width - new_width) / 2
    y = (a4_height - new_height) / 2

    c = canvas.Canvas(output_pdf_path, pagesize=A4)
    c.drawImage(image_path, x, y, width=new_width, height=new_height)
    c.showPage()
    c.save()
    print(f"PDF saved as {output_pdf_path} with {margin_mm}mm margin")

image_to_centered_pdf("C:/Users/Josuan/Desktop/bogoballers-server/test/image3.png", "output.pdf")
