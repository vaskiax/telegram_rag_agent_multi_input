import os
import matplotlib
# Ensure writable config directory for Matplotlib in Cloud Run
os.environ['MPLCONFIGDIR'] = '/tmp'
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io

def render_latex_to_image(latex_str: str) -> io.BytesIO:
    """
    Renders a LaTeX string into an image buffer (PNG).
    """
    # Create figure with transparent background
    # Lower DPI prevents "Giant Image" syndrome on mobile
    fig = plt.figure(figsize=(0.1, 0.1), dpi=200)
    fig.patch.set_facecolor('none')
    fig.patch.set_alpha(0.0)

    # Add text (equation)
    # We use a black text by default, but for Telegram dark mode compat, 
    # white or a box might be better. Let's try standard black first, 
    # usually Telegram handles transparent PNGs well with adapted background or we can add a white background.
    # Actually, a white background is safer for legibility on all themes.
    
    # Adding text (using raw string for latex)
    # We wrap it in $...$ if not present, but usually agent sends block \[ ... \]
    
    clean_latex = latex_str.strip()
    
    # Remove standard block markers if they exist to start fresh
    if clean_latex.startswith("\\[") and clean_latex.endswith("\\]"):
        clean_latex = clean_latex[2:-2].strip()
    if clean_latex.startswith("$$") and clean_latex.endswith("$$"):
        clean_latex = clean_latex[2:-2].strip()
        
    wrapped_latex = f"${clean_latex}$"

    # Render text
    plt.text(0.5, 0.5, wrapped_latex, fontsize=14, ha='center', va='center')
    plt.axis('off')

    # Save to buffer
    buf = io.BytesIO()
    
    # Use bbox_inches='tight' to crop effectively
    # Reduced pad_inches to minimize whitespace
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, transparent=False, facecolor='white')
    plt.close(fig)
    buf.seek(0)
    
    return buf
