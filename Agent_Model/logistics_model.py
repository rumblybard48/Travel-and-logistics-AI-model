import os
import re
import time
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import openrouteservice
import folium
from streamlit_folium import st_folium

load_dotenv()

OPEN_ROUTE_SERVICE_APIKEY = os.getenv("OPEN_ROUTE_SERVICE_APIKEY")
client = openrouteservice.Client(key=OPEN_ROUTE_SERVICE_APIKEY)

geolocator = Nominatim(user_agent="logistics_ai_tool")

LOGISTICS_SYSTEM_PROMPT = """
You are an expert logistics coordinator and supply chain advisor with deep knowledge of 
global shipping, freight, customs, and warehousing.

Your responsibilities:
- Help users estimate shipping costs by truck or air freight
- Recommend appropriate storage conditions for products
- Compare shipping modes and help users make cost-effective decisions
- Ask for missing details (weight, origin, destination, product type) before estimating
- Present cost comparisons clearly, highlighting trade-offs between speed and cost
- Always clarify whether costs are estimates and may vary with real carriers

IMPORTANT: Whenever you call estimate_shipping_cost_by_location, estimate_air_freight_cost,
or compare_shipping_modes, always end your reply with a line in exactly this format:
MAP: <origin> | <destination>
Replace <origin> and <destination> with the exact location names used in the tool call.

Tone: professional, concise, and helpful. Avoid jargon unless the user is clearly an expert.
"""


# ── Retry helper ──────────────────────────────────────────────────────────────

def _retry(fn, retries=3, delay=2):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(delay * (2 ** attempt))


# ── Geocoding ─────────────────────────────────────────────────────────────────

def get_coordinates(location_name: str):
    """
    Returns [longitude, latitude] for a given location name, or None if not found.

    Args:
        location_name (str): City, country, or address to look up.

    Returns:
        list | None: [longitude, latitude] or None.
    """
    location = _retry(lambda: geolocator.geocode(location_name))
    if location:
        return [location.longitude, location.latitude]
    return None


def _geocode(location_name: str):
    """Returns a geopy Location object or None."""
    return _retry(lambda: geolocator.geocode(location_name))


def _get_geodesic_km(origin: str, destination: str):
    loc1 = _geocode(origin)
    loc2 = _geocode(destination)
    if not loc1 or not loc2:
        return None
    return geodesic((loc1.latitude, loc1.longitude), (loc2.latitude, loc2.longitude)).kilometers


# ── Map rendering ─────────────────────────────────────────────────────────────

def render_route_map(origin: str, destination: str):
    """
    Renders a folium map with markers for origin and destination,
    and a straight line connecting them.
    """
    loc1 = _geocode(origin)
    loc2 = _geocode(destination)

    if not loc1 or not loc2:
        st.warning("Could not render map: one or both locations not found.")
        return

    mid_lat = (loc1.latitude + loc2.latitude) / 2
    mid_lon = (loc1.longitude + loc2.longitude) / 2

    # Zoom level based on distance
    dist_km = geodesic(
        (loc1.latitude, loc1.longitude),
        (loc2.latitude, loc2.longitude)
    ).kilometers
    if dist_km < 50:
        zoom = 10
    elif dist_km < 300:
        zoom = 7
    elif dist_km < 1500:
        zoom = 5
    else:
        zoom = 3

    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=zoom, tiles="CartoDB positron")

    # Origin marker (green)
    folium.Marker(
        location=[loc1.latitude, loc1.longitude],
        popup=folium.Popup(f"<b>Origin</b><br>{origin}", max_width=200),
        tooltip=f"Origin: {origin}",
        icon=folium.Icon(color="green", icon="arrow-up", prefix="fa")
    ).add_to(m)

    # Destination marker (red)
    folium.Marker(
        location=[loc2.latitude, loc2.longitude],
        popup=folium.Popup(f"<b>Destination</b><br>{destination}", max_width=200),
        tooltip=f"Destination: {destination}",
        icon=folium.Icon(color="red", icon="flag", prefix="fa")
    ).add_to(m)

    # Route line
    folium.PolyLine(
        locations=[
            [loc1.latitude, loc1.longitude],
            [loc2.latitude, loc2.longitude]
        ],
        color="#2563eb",
        weight=3,
        opacity=0.8,
        dash_array="8 4",
        tooltip=f"{dist_km:.0f} km straight-line"
    ).add_to(m)

    # Distance label at midpoint
    folium.Marker(
        location=[mid_lat, mid_lon],
        icon=folium.DivIcon(
            html=f"""
                <div style="
                    background: white;
                    border: 1px solid #2563eb;
                    border-radius: 6px;
                    padding: 3px 8px;
                    font-size: 12px;
                    font-weight: 600;
                    color: #2563eb;
                    white-space: nowrap;
                    box-shadow: 0 1px 4px rgba(0,0,0,0.15);
                ">{dist_km:.0f} km</div>
            """,
            icon_size=(80, 28),
            icon_anchor=(40, 14)
        )
    ).add_to(m)

    st.markdown("#### Route map")
    st_folium(m, width="100%", height=380, returned_objects=[])


# ── Storage Recommendation ────────────────────────────────────────────────────

def recommend_storage_type(product_name: str) -> str:
    """
    Recommends optimal storage conditions for a product using AI reasoning.

    Args:
        product_name (str): The name of the product (e.g. 'frozen salmon', 'lithium batteries').

    Returns:
        str: Storage recommendation with brief reasoning.
    """
    from google.generativeai import GenerativeModel
    model = GenerativeModel(model_name="gemini-2.5-flash")
    prompt = (
        f"What type of storage is ideal for '{product_name}'? "
        "Consider whether it is perishable, temperature-sensitive, hazardous, or prone to spoilage. "
        "Reply with one category: 'room temperature', 'cold storage (2–8°C)', "
        "'frozen storage (below -18°C)', 'dry storage', or 'hazardous materials storage'. "
        "Then give a 1-2 sentence explanation."
    )
    response = model.generate_content(prompt)
    return response.text.strip()


# ── Truck Shipping ─────────────────────────────────────────────────────────────

def estimate_shipping_cost_by_location(
    origin: str,
    destination: str,
    weight_kg: float,
    volume_m3: float = 0.0,
    service_type: str = "standard"
) -> str:
    """
    Estimates road freight cost between two locations by truck.

    Args:
        origin (str): Origin city or address.
        destination (str): Destination city or address.
        weight_kg (float): Actual cargo weight in kilograms.
        volume_m3 (float): Cargo volume in cubic metres. Default 0.
        service_type (str): 'standard' or 'express'. Default 'standard'.

    Returns:
        str: Estimated cost with breakdown.
    """
    if weight_kg <= 0:
        return "Error: weight_kg must be greater than 0."

    origin_coords = get_coordinates(origin)
    destination_coords = get_coordinates(destination)

    if not origin_coords or not destination_coords:
        return "Error: Could not determine coordinates for one or both locations."

    try:
        route = _retry(lambda: client.directions(
            coordinates=[origin_coords, destination_coords],
            profile="driving-hgv",
            format="geojson"
        ))
        distance_km = route["features"][0]["properties"]["summary"]["distance"] / 1000
    except Exception as e:
        return f"Error fetching route: {e}"

    volumetric_weight_kg = volume_m3 * 333
    chargeable_weight = max(weight_kg, volumetric_weight_kg)

    rate_per_km_per_kg = 0.00012 if service_type == "standard" else 0.00025
    base_cost = 15.0
    fuel_surcharge = 0.18

    subtotal = base_cost + (chargeable_weight * rate_per_km_per_kg * distance_km)
    total = subtotal * (1 + fuel_surcharge)

    vol_note = (
        f"\n  Volumetric weight: {volumetric_weight_kg:.1f} kg  |  Chargeable weight: {chargeable_weight:.1f} kg"
        if volume_m3 > 0 else ""
    )

    return (
        f"🚚 Road Freight Estimate ({service_type.title()})\n"
        f"  Route: {origin} → {destination}  ({distance_km:.1f} km)\n"
        f"  Actual weight: {weight_kg} kg{vol_note}\n"
        f"  Subtotal: ${subtotal:.2f}  |  Fuel surcharge (18%): ${subtotal * fuel_surcharge:.2f}\n"
        f"  ── Estimated Total: ${total:.2f} USD ──\n"
        f"  ⚠️ Estimate only — actual carrier rates will vary."
    )


# ── Air Freight ───────────────────────────────────────────────────────────────

def estimate_air_freight_cost(
    origin: str,
    destination: str,
    weight_kg: float,
    volume_m3: float = 0.0,
    service_class: str = "economy"
) -> str:
    """
    Estimates international air freight cost between two cities or airports.

    Args:
        origin (str): Origin city or airport name.
        destination (str): Destination city or airport name.
        weight_kg (float): Actual cargo weight in kilograms.
        volume_m3 (float): Cargo volume in cubic metres. Default 0.
        service_class (str): 'economy' or 'express'. Default 'economy'.

    Returns:
        str: Estimated cost with breakdown.
    """
    if weight_kg <= 0:
        return "Error: weight_kg must be greater than 0."

    distance_km = _get_geodesic_km(origin, destination)
    if distance_km is None:
        return "Error: Could not resolve one or both locations."

    volumetric_weight_kg = volume_m3 * 167
    chargeable_weight = max(weight_kg, volumetric_weight_kg)

    rate_per_km_per_kg = 0.00045 if service_class == "economy" else 0.00085
    base_cost = 75.0
    fuel_surcharge = 0.22
    security_fee = 0.50 * chargeable_weight

    subtotal = base_cost + (chargeable_weight * rate_per_km_per_kg * distance_km) + security_fee
    total = subtotal * (1 + fuel_surcharge)

    vol_note = (
        f"\n  Volumetric weight: {volumetric_weight_kg:.1f} kg  |  Chargeable weight: {chargeable_weight:.1f} kg"
        if volume_m3 > 0 else ""
    )

    return (
        f"✈️ Air Freight Estimate ({service_class.title()})\n"
        f"  Route: {origin} → {destination}  ({distance_km:.0f} km straight-line)\n"
        f"  Actual weight: {weight_kg} kg{vol_note}\n"
        f"  Security fee: ${security_fee:.2f}  |  Fuel surcharge (22%): ${subtotal * fuel_surcharge:.2f}\n"
        f"  ── Estimated Total: ${total:.2f} USD ──\n"
        f"  ⚠️ Estimate only — actual carrier rates will vary."
    )


# ── Mode Comparison ───────────────────────────────────────────────────────────

def compare_shipping_modes(
    origin: str,
    destination: str,
    weight_kg: float,
    volume_m3: float = 0.0
) -> str:
    """
    Compares standard road freight vs economy air freight side-by-side.

    Args:
        origin (str): Origin city.
        destination (str): Destination city.
        weight_kg (float): Cargo weight in kilograms.
        volume_m3 (float): Cargo volume in cubic metres. Default 0.

    Returns:
        str: Side-by-side comparison of road and air options.
    """
    truck = estimate_shipping_cost_by_location(origin, destination, weight_kg, volume_m3, "standard")
    air = estimate_air_freight_cost(origin, destination, weight_kg, volume_m3, "economy")

    return (
        f"📦 Shipping Mode Comparison: {origin} → {destination}\n\n"
        f"{truck}\n\n"
        f"{air}\n\n"
        f"💡 Tip: Choose road freight for cost savings on non-urgent shipments. "
        f"Choose air for time-sensitive or high-value cargo."
    )


# ── Customs Duty Estimate ─────────────────────────────────────────────────────

def estimate_customs_duty(
    product: str,
    origin_country: str,
    destination_country: str,
    declared_value_usd: float
) -> str:
    """
    Provides a rough customs duty estimate using AI reasoning about typical tariff rates.

    Args:
        product (str): Description of the product being shipped.
        origin_country (str): Country of origin.
        destination_country (str): Destination country.
        declared_value_usd (float): Declared value of the shipment in USD.

    Returns:
        str: Estimated duty range and notes.
    """
    from google.generativeai import GenerativeModel
    model = GenerativeModel(model_name="gemini-2.5-flash")
    prompt = (
        f"A shipment of '{product}' is being sent from {origin_country} to {destination_country}. "
        f"The declared value is ${declared_value_usd:.2f} USD. "
        "What is the typical import duty rate range for this product in the destination country? "
        "Provide an estimated duty amount in USD based on the declared value. "
        "Mention any relevant trade agreements (e.g. free trade zones, GSP). "
        "Keep the answer concise (3-5 sentences) and note that actual rates should be verified with a customs broker."
    )
    response = model.generate_content(prompt)
    return f"🛃 Customs Duty Estimate\n{response.text.strip()}"


# ── Streamlit UI ──────────────────────────────────────────────────────────────

def _extract_map_locations(text: str):
    """
    Parses 'MAP: <origin> | <destination>' from the AI reply.
    Returns (origin, destination) tuple or (None, None).
    """
    match = re.search(r"MAP:\s*(.+?)\s*\|\s*(.+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, None


def run_logistics_model():
    st.subheader("🚚 Logistics Assistant")

    try:
        model = _configure_logistics_model()
    except ValueError as ve:
        st.error(str(ve))
        return

    if "logistics_chat" not in st.session_state:
        st.session_state.logistics_chat = model.start_chat(enable_automatic_function_calling=True)
        st.session_state.logistics_history = []  # list of (user_msg, bot_msg, origin, destination)

    # Render history
    for entry in st.session_state.logistics_history:
        user_msg, bot_msg, origin, destination = entry

        with st.chat_message("user"):
            st.markdown(user_msg)

        with st.chat_message("assistant"):
            # Strip the MAP: line before displaying
            display_msg = re.sub(r"\nMAP:.*$", "", bot_msg, flags=re.IGNORECASE | re.MULTILINE).strip()
            st.markdown(display_msg)
            if origin and destination:
                render_route_map(origin, destination)

    # New input
    user_input = st.chat_input("Ask your logistics assistant...")

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = st.session_state.logistics_chat.send_message(user_input)
                    bot_reply = response.text.strip()

                    origin, destination = _extract_map_locations(bot_reply)

                    display_msg = re.sub(r"\nMAP:.*$", "", bot_reply, flags=re.IGNORECASE | re.MULTILINE).strip()
                    st.markdown(display_msg)

                    if origin and destination:
                        render_route_map(origin, destination)

                    st.session_state.logistics_history.append((user_input, bot_reply, origin, destination))
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.session_state.logistics_history:
        if st.button("🗑️ Clear conversation", key="clear_logistics"):
            st.session_state.logistics_chat = None
            st.session_state.logistics_history = []
            st.rerun()


# ── Model Configuration ───────────────────────────────────────────────────────

def _configure_logistics_model():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY in .env")
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=LOGISTICS_SYSTEM_PROMPT,
        tools=[
            recommend_storage_type,
            estimate_shipping_cost_by_location,
            estimate_air_freight_cost,
            compare_shipping_modes,
            estimate_customs_duty,
            get_coordinates,
        ]
    )
    return model