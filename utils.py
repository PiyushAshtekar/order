import os
import random
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def generate_token():
    """Generate a unique token number for the order."""
    return f"RB{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

def calculate_total(items):
    """Calculate the total bill amount."""
    return sum(float(item.get('price', 0)) * int(item.get('quantity', 0)) for item in items)

def generate_order_pdf(order_data, token):
    """Generate a PDF document with order details.
    
    Args:
        order_data (dict): Order details including items and customer comment
        token (str): Unique order token number
    
    Returns:
        str: Path to the generated PDF file
    """
    # Create temp directory if it doesn't exist
    if not os.path.exists('temp'):
        os.makedirs('temp')
    
    # PDF file path
    pdf_path = f'temp/order_{token}.pdf'
    
    # Create PDF document
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    
    # Content elements
    elements = []
    
    # Title
    elements.append(Paragraph("Raju Burger - Order Confirmation", title_style))
    elements.append(Spacer(1, 12))
    
    # Order details
    elements.append(Paragraph(f"Order Token: {token}", styles['Heading2']))
    elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Items table
    items_data = [["Item", "Quantity", "Price", "Total"]]
    total_amount = 0
    
    for item in order_data['items']:
        quantity = int(item.get('quantity', 0))
        price = float(item.get('price', 0))
        item_total = quantity * price
        total_amount += item_total
        
        items_data.append([
            item.get('name', ''),
            str(quantity),
            f"₹{price:.2f}",
            f"₹{item_total:.2f}"
        ])
    
    # Add total row
    items_data.append(["Total", "", "", f"₹{total_amount:.2f}"])
    
    # Create table
    table = Table(items_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Add customer comment if provided
    if order_data.get('comment'):
        elements.append(Paragraph("Customer Comment:", styles['Heading3']))
        elements.append(Paragraph(order_data['comment'], styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    return pdf_path