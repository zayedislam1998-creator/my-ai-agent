import streamlit as st
import google.generativeai as genai
import requests
import os
import json
import base64
import pandas as pd
import urllib3
import io

# SSL ওয়ার্নিং বন্ধ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. CONFIGURATION
# ==========================================
st.set_page_config(page_title="WP Smart Assistant", layout="wide", page_icon="🤖")

# API KEYS
GENAI_API_KEY = "AIzaSyCKv5shmVB5BWbbEioRENKZeosR9OAkeO0"
os.environ["GEMINI_API_KEY"] = GENAI_API_KEY
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# ==========================================
# 2. CORE CLASS: WP MANAGER (With Fixes)
# ==========================================
class WPManager:
    def __init__(self, url, user, password, wc_key=None, wc_secret=None):
        self.url = url.rstrip('/')
        self.user = user
        self.password = password
        self.wc_key = wc_key
        self.wc_secret = wc_secret
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        self.core_headers = {
            "Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode(),
            "Content-Type": "application/json",
            "User-Agent": self.user_agent
        }

    def test_connection(self):
        try:
            r = requests.get(f"{self.url}/wp-json/wp/v2/users/me", headers=self.core_headers, verify=False, timeout=10)
            return r.status_code == 200
        except: return False

    def create_product(self, product_data):
        endpoint = "wc/v3/products"
        params = {"consumer_key": self.wc_key, "consumer_secret": self.wc_secret}
        headers = {"User-Agent": self.user_agent, "Content-Type": "application/json"}
        
        try:
            r = requests.post(f"{self.url}/wp-json/{endpoint}", json=product_data, params=params, headers=headers, verify=False)
            return r
        except Exception as e:
            return None

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def parse_file(uploaded_file):
    """ফাইল থেকে টেক্সট বা ডাটাফ্রেমে কনভার্ট করে"""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            return df.to_json(orient='records')
        elif uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
            return df.to_json(orient='records')
        else: # Text file
            return uploaded_file.read().decode("utf-8")
    except Exception as e:
        return f"Error reading file: {str(e)}"

def chat_with_ai(prompt, file_context, chat_history):
    """Gemini AI এর সাথে চ্যাট করার ফাংশন"""
    
    system_instruction = """
    You are a Smart E-commerce Manager Assistant. 
    Your Goal: Help the user analyze product data files and prepare them for WooCommerce upload.
    
    Capabilities:
    1. Analyze uploaded CSV/Excel/Text data (identify product names, prices, descriptions).
    2. Answer questions about the data (e.g., "How many shirts?", "What is the average price?").
    3. Modify data based on user request (e.g., "Add 10% to all prices", "Set category to 'Saree'").
    4. PREPARE JSON FOR UPLOAD: If the user says "Upload" or "Import", you MUST output a VALID JSON block inside specific tags <JSON_START> and <JSON_END>.
    
    Format for Upload JSON:
    <JSON_START>
    [
        {
            "name": "Product Name",
            "regular_price": "100",
            "description": "Full description",
            "short_description": "Short summary",
            "categories": [{"id": 1}] (If category ID known, else omit or guess)
        }
    ]
    <JSON_END>
    
    Always be polite and helpful. Speak in the language the user is using (mostly Bengali/English).
    """
    
    full_prompt = f"""
    {system_instruction}
    
    CONTEXT (UPLOADED FILE DATA):
    {file_context[:10000]} (Truncated if too long)
    
    CHAT HISTORY:
    {chat_history}
    
    USER: {prompt}
    ASSISTANT:
    """
    
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return "AI Error: " + str(e)

# ==========================================
# 4. MAIN APP UI
# ==========================================
st.title("🛒 Smart Shop Manager (AI Chat)")

# --- SIDEBAR: SETTINGS & UPLOAD ---
with st.sidebar:
    st.header("⚙️ Setup")
    
    # Creds
    with st.expander("API Credentials", expanded=False):
        wp_url = st.text_input("Site URL", "https://visa.showrove.online")
        wp_user = st.text_input("WP Username", "Zayedulislam33")
        wp_pass = st.text_input("WP Password", type="password")
        wc_key = st.text_input("WC Consumer Key")
        wc_secret = st.text_input("WC Consumer Secret")
        
        if st.button("Check Connection"):
            bot = WPManager(wp_url, wp_user, wp_pass, wc_key, wc_secret)
            if bot.test_connection(): st.success("Connected!")
            else: st.error("Connection Failed")

    # File Uploader
    st.markdown("---")
    st.header("📂 Data Source")
    uploaded_file = st.file_uploader("Upload Product File (CSV, Excel, Txt)", type=['csv', 'xlsx', 'txt'])
    
    # Process File
    file_content = ""
    if uploaded_file:
        file_content = parse_file(uploaded_file)
        st.success(f"File Loaded: {uploaded_file.name}")
        with st.expander("See Raw Data"):
            st.write(file_content[:500] + "...")

    # Reset Chat
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# --- MAIN CHAT INTERFACE ---

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_products" not in st.session_state:
    st.session_state.pending_products = []

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("Ask about your file or tell me to upload..."):
    # 1. Show User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Get AI Response
    with st.spinner("Analyzing..."):
        # Prepare history string
        history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages[-5:]])
        
        ai_reply = chat_with_ai(prompt, file_content, history_text)
        
        # 3. Check for JSON Action (Upload Request)
        clean_reply = ai_reply
        products_to_upload = []
        
        if "<JSON_START>" in ai_reply and "<JSON_END>" in ai_reply:
            try:
                json_str = ai_reply.split("<JSON_START>")[1].split("<JSON_END>")[0]
                products_to_upload = json.loads(json_str)
                clean_reply = ai_reply.split("<JSON_START>")[0] # Hide JSON from chat view
                st.session_state.pending_products = products_to_upload
            except:
                clean_reply += "\n[System Error: Failed to parse product data]"

        # 4. Show AI Message
        st.session_state.messages.append({"role": "assistant", "content": clean_reply})
        with st.chat_message("assistant"):
            st.markdown(clean_reply)
            
            # 5. Show Action Button if Products Detected
            if products_to_upload:
                st.success(f"🎯 AI has prepared {len(products_to_upload)} products for upload!")
                st.json(products_to_upload) # Preview
                
                col1, col2 = st.columns(2)
                if col1.button("✅ Confirm & Upload to Website"):
                    bot = WPManager(wp_url, wp_user, wp_pass, wc_key, wc_secret)
                    progress = st.progress(0)
                    success_count = 0
                    
                    for i, prod in enumerate(products_to_upload):
                        res = bot.create_product(prod)
                        if res and res.status_code == 201:
                            success_count += 1
                        progress.progress((i + 1) / len(products_to_upload))
                    
                    st.toast(f"🎉 Uploaded {success_count}/{len(products_to_upload)} products successfully!")
                    st.session_state.pending_products = [] # Clear pending