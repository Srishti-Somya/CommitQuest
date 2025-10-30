import streamlit as st
from streamlit import session_state as sst
# We no longer need fetch_star_count, so that import is removed.

TOKEN = st.secrets["token"]

def base_ui():
    """
    ### Sets up the base user interface for the Streamlit application.

    This function performs the following tasks:
    1. Configures the Streamlit page settings.
    2. Initializes the Streamlit session state.
    3. Displays the title bar and input fields.
    4. Creates a sidebar with a form.
    """

    # Streamlit Page Config
    page_config()

    # Initialise streamlit session state
    initialize_sst()

    # Title and input
    title_bar()

    with st.sidebar:
        form() # Streamlit Form

        if sst.username and sst.token and sst.button_pressed:
            nav_ui() # Sidebar navigation menu

        # This is the new project guide, un-commented and active
        how_to_use()
        
        # The promo() call has been deleted from here


def page_config():
    """
    ### Configures the Streamlit page settings.

    This function sets the page title, icon, layout, and menu items for the Streamlit app.
    The app is designed to track GitHub contributions and provide insights into user activity.

    Menu Items:
        - About: Provides information about the app and its developers.
    """

    st.set_page_config(
        page_title = "CommitQuest - Monitor your GitHub Stats",
        page_icon = "./static/icon.png", # You can change this to your own icon
        layout = "wide",
        menu_items={
            "About": """
            This is a Streamlit app that tracks GitHub contributions and provides insights into activity.
            """
            # You can update the "About" text to be about your version
            }
    )

def initialize_sst():
    """
    ### Initialize the session state with default values if they are not already set.
    This function checks if certain keys are present in the session state (sst).

    If any of these keys are missing, it initializes them with default values:
    - 'username': an empty string
    - 'user_token': an empty string
    - 'token_present': False
    - 'button_pressed': False
    """

    # Initializing session state
    if 'username' not in sst:
        sst.username = ''
    if 'user_token' not in sst:
        sst.user_token = ''
    if 'token_present' not in sst:
        sst.token_present = False
    if 'button_pressed' not in sst:
        sst.button_pressed = False

def title_bar():
    """
    ### Creates a title bar for the Streamlit UI with the title "GitHub Stats".
    
    The original star button has been removed from this function.
    """
    
    # The columns and star button have been removed.
    st.title("GitHub Stats")
    # You can change the title to "CommitQuest" or your project name here
    

def form():
    """
    ### Creates a form in a Streamlit container for GitHub username and optional personal access token input.

    The form includes:
    - A text input for the GitHub username.
    - A toggle to indicate if the user has a GitHub Access Token.
    - A conditional text input for the GitHub Personal Access Token if the toggle is enabled.
    - A button to trigger the analysis.

    Updates the global state variables `sst.username`, `sst.token_present`, `sst.user_token`, `sst.token`, and `sst.button_pressed` based on user input.
    """

    form = st.container(border=True)
    sst.username = form.text_input("Enter GitHub Username:", value=sst.username)
    
    if form.toggle("I have a GitHub Access Token", value=sst.token_present, help="Toggle if you have a token. Create [Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic)"):
        sst.token_present = True
    else:
        sst.token_present = False
    
    # Add warning about token permissions if showing private contributions
    if sst.token_present:
        sst.user_token = form.text_input("Enter GitHub Personal Access Token:", value=sst.user_token, type="password")
        sst.token = sst.user_token
    else:
        sst.token = TOKEN
    
    if form.button("Analyze", type="primary"):
        sst.button_pressed = True

def how_to_use():
    """
    ### Displays an expander with instructions on how to use this tool.
    
    This is the new "Project Guide" section.
    """

    with st.expander("❓ Project Guide"):
        st.write("""
        **Welcome to your GitHub Stats Analyzer!**

        1.  **Enter Username:** * Type any public GitHub username into the text box above.

        2.  **Add Token (Optional):**
            * To see stats for your **private** repositories, you must provide a GitHub Personal Access Token.
            * Toggle "I have a GitHub Access Token."
            * Paste your token into the password field.
            * If you only want to see public stats, you can leave this toggled off.

        3.  **Analyze:** * Click the "Analyze" button to fetch the data.
        
        4.  **Explore:** * Use the "Overview" and "Predictions" tabs (which appear after analysis) to see your contribution data.
        """)


def nav_ui():
    """
    ### Creates the navigation sidebar UI for the GitHub stats checker application.
    This function adds navigation links to the sidebar using Streamlit's `st.page_link` method.
    The sidebar contains links to the "Overview" and "Predictions" pages, each with an icon and a help tooltip.
    
    **Sidebar Links:**
    - Overview: Links to "app.py" with a star icon and a tooltip for checking GitHub stats and contributions.
    - Predictions: Links to "./pages/predictions.py" with a lightning bolt icon and a tooltip for predicting GitHub contributions.
    """

    with st.sidebar.container(border=True):
        col1, col2 = st.columns(2)
        col1.page_link(
            "app.py", 
            label="Overview", 
            icon="✨",
            help="ℹ️ Check your GitHub stats and contributions.",
            use_container_width=True
            )
        col2.page_link(
            "./pages/predictions.py", 
            label="Predictions", 
            icon="⚡",
            help="ℹ️ Predict your GitHub contributions.",
            use_container_width=True
            )

# The 'promo()' function definition has been completely deleted.

def growth_stats(total_contributions:int, contribution_rate:int, active_days:int, total_days:int, percent_active_days:float, since:str):
    col1, col2 = st.columns(2)
    col1.metric(
        label=f"Total Contributions {since}", 
        value=f"{total_contributions} commits",
        delta=f"{contribution_rate:.2f} contributions/day",
        delta_color="inverse" if contribution_rate < 1 else "normal"
        )
    
    col2.metric(
        label="Active Days", 
        value=f"{active_days}/{total_days} days",
        delta=f"{percent_active_days:.1f}% days active",
        delta_color="inverse" if percent_active_days < 8 else "normal"
        )
