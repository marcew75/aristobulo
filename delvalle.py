import streamlit as st
from streamlit_folium import st_folium
import folium
import googlemaps
import requests
from urllib.parse import urlparse
import re
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from pathlib import Path

# Configuración de la aplicación
st.set_page_config(page_title="Mapa Interactivo con Extracción de Correos", layout="wide")

# Función para cargar CSS
def load_css():
    css_file = Path(__file__).parent / "styles" / "style.css"
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Cargar CSS al inicio de la aplicación
try:
    load_css()
except Exception as e:
    st.warning(f"No se pudo cargar el archivo CSS: {str(e)}")

# Footer
st.markdown("""
    <div class='footer' style="text-align: center; margin-top: 20px;">
        <img src="images/Captura de pantalla 2024-11-25 082805.png" alt="Logo" style="width: 100px;"><br>
        <p>Desarrollado con ❤️ por Marce Data</p>
    </div>
""", unsafe_allow_html=True)

# Funciones de utilidad
def is_valid_url(url):
    """Valida si una URL es válida y cumple con ciertos criterios."""
    try:
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            return False
        excluded_domains = ['facebook.com', 'twitter.com', 'instagram.com']
        if any(domain in parsed.netloc for domain in excluded_domains):
            return False
        return True
    except Exception:
        return False

def extract_emails(text):
    """Extrae correos electrónicos de un texto usando expresiones regulares."""
    if not text:  # Validación adicional para texto nulo
        return []
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(email_pattern, text)))

def scrape_page(url):
    """Extrae el contenido HTML de una página web."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        st.warning(f"Error al acceder a {url}: {str(e)}")
        return ""

def scrape_emails_from_urls(urls, max_workers=5):
    """Extrae correos electrónicos de una lista de URLs usando múltiples hilos."""
    if not urls:  # Validación para lista vacía de URLs
        return []
        
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        html_contents = list(executor.map(scrape_page, urls))
        
    for url, html_content in zip(urls, html_contents):
        if html_content:
            emails = extract_emails(html_content)
            for email in emails:
                results.append([url, email])
    
    return results

st.title("Mapa Interactivo con Extracción de Correos")

# Inicializar variables de estado si no existen
if 'map_clicked' not in st.session_state:
    st.session_state.map_clicked = False
if 'last_lat' not in st.session_state:
    st.session_state.last_lat = None
if 'last_lng' not in st.session_state:
    st.session_state.last_lng = None

# Configuración inicial del mapa
default_lat = 40.4168  # Latitud inicial (Madrid)
default_lng = -3.7038  # Longitud inicial (Madrid)

# Inicializar API de Google Maps
try:
    api_key = st.secrets["google_maps_api_key"]
    gmaps = googlemaps.Client(key=api_key)
except Exception as e:
    st.error("Error al inicializar Google Maps API. Verifica tu API key.")
    st.stop()

# Crear un mapa centrado en la ubicación inicial
m = folium.Map(location=[default_lat, default_lng], zoom_start=12)
folium.ClickForMarker().add_to(m)

# Renderizar el mapa con streamlit-folium
map_data = st_folium(m, width=700, height=500)

# Verificar si el usuario hizo clic en el mapa
if map_data and map_data.get("last_clicked"):
    last_clicked = map_data["last_clicked"]
    if last_clicked.get("lat") is not None and last_clicked.get("lng") is not None:
        lat = last_clicked["lat"]
        lng = last_clicked["lng"]
        st.session_state.map_clicked = True
        st.session_state.last_lat = lat
        st.session_state.last_lng = lng

        # Mostrar las coordenadas seleccionadas
        st.write(f"Coordenadas seleccionadas: Latitud {lat:.6f}, Longitud {lng:.6f}")

        try:
            # Obtener la dirección de las coordenadas usando Google Maps API
            geocode_result = gmaps.reverse_geocode((lat, lng))
            if geocode_result:
                address = geocode_result[0]['formatted_address']
                st.write(f"Dirección aproximada: {address}")

                # Buscar lugares cercanos con Google Places API
                categoria = st.selectbox(
                    "Selecciona una categoría para buscar lugares cercanos",
                    ["restaurant", "hotel", "store", "cafe", "bar", "hospital", "park"]
                )

                if st.button("Buscar lugares"):
                    with st.spinner("Buscando lugares..."):
                        places_result = gmaps.places_nearby(
                            location=(lat, lng),
                            radius=5000,
                            type=categoria
                        )

                        if places_result and places_result.get('results'):
                            st.write(f"Lugares cercanos encontrados en la categoría '{categoria}':")
                            urls = []
                            for place in places_result['results']:
                                name = place.get('name', 'Sin nombre')
                                vicinity = place.get('vicinity', 'Sin dirección')
                                
                                try:
                                    place_details = gmaps.place(
                                        place_id=place['place_id'],
                                        fields=['name', 'website']
                                    )
                                    website = place_details.get('result', {}).get('website')
                                except Exception as e:
                                    st.warning(f"Error al obtener detalles de {name}: {str(e)}")
                                    website = None

                                st.write(f"📍 {name}")
                                st.write(f"Dirección: {vicinity}")
                                if website:
                                    st.write(f"🌐 Sitio web: {website}")
                                    if is_valid_url(website):
                                        urls.append(website)
                                st.write("---")

                            if urls:
                                st.write("Extrayendo correos electrónicos de los sitios web encontrados...")
                                emails = scrape_emails_from_urls(urls)
                                if emails:
                                    st.write("Correos electrónicos encontrados:")
                                    for url, email in emails:
                                        st.write(f"📧 {email} (extraído de {url})")
                                    
                                    df = pd.DataFrame(emails, columns=["sitios", "correos"])
                                    csv = df.to_csv(index=False).encode("utf-8")
                                    st.download_button("Descargar CSV", csv, "emails.csv", "text/csv")
                                else:
                                    st.info("No se encontraron correos electrónicos en los sitios analizados.")
                            else:
                                st.info("No se encontraron sitios web válidos para analizar.")
                        else:
                            st.info(f"No se encontraron lugares en la categoría '{categoria}'.")
        except Exception as e:
            st.error(f"Error en la búsqueda: {str(e)}")
    else:
        st.warning("Las coordenadas seleccionadas no son válidas.")
else:
    st.write("Haz clic en el mapa para seleccionar un punto.")
