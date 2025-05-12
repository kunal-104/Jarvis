import pyautogui
import time
import pyttsx3
import os
import json
import base64
import io
from PIL import ImageGrab, Image
import google.generativeai as genai
import platform
import logging
import webbrowser
import subprocess
import re




# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("jarvis.log"),
        logging.StreamHandler()
    ]
)

class JarvisAssistant:
    def __init__(self, gemini_api_key, maintain_context=True):
        self.gemini_api_key = gemini_api_key
        self.maintain_context = maintain_context
        self.conversation_history = []
        self.system_info = {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "platform_release": platform.release(),
            "architecture": platform.machine()
        }
        
        # logging.info(f"System info: {self.system_info}")
        
        # Initialize Gemini
        genai.configure(api_key=self.gemini_api_key)
        
        # Get screen size
        self.screen_width, self.screen_height = pyautogui.size()
        # logging.info(f"Screen resolution: {self.screen_width}x{self.screen_height}")
        
        # Initialize Text-to-Speech
        self.voice_engine = pyttsx3.init()
        self.voice_engine.setProperty('rate', 150)
        self.voice_engine.setProperty('volume', 0.9)
        
        voices = self.voice_engine.getProperty('voices')

        for voice in voices:
            print(f"Voice: {voice.name}, ID: {voice.id}")

        # Choose a female voice (example: on Windows, 'Zira'; on macOS, 'Samantha')
        # for voice in voices:
        #     if "female" in voice.name.lower() or "zira" in voice.name.lower() or "samantha" in voice.id.lower():
        #         self.voice_engine.setProperty('voice', voice.id)
        #         break
        for voice in voices:
            if "male" in voice.name.lower():
                self.voice_engine.setProperty('voice', voice.id)
                break

                # Store UI element maps for different applications
        self.ui_element_maps = {}
        
        # Predefined functions for common tasks
        self.common_tasks = {
            "open_browser": self.open_browser,
            "search_youtube": self.search_youtube,
            "search_google": self.search_google,
            "open_file_explorer": self.open_file_explorer,
            "check_weather": self.check_weather,
            "check_news": self.check_news
        }
        
        # Maximum verification attempts before giving up
        self.max_verification_attempts = 5

        # Initialize managers
        self.ui_manager = UIAutomationManager(self)
        self.web_manager = WebAutomationManager(self)
        self.task_manager = TaskManager(self)
        self.local_ai = LocalAIManager(model_name="deepseek-r1:1.5b")
        # self.local_ai = LocalAIManager(model_name="phi3")
        self.local_ai.start_model()

        self.animation = JarvisRingAnimation()
        self.animation.auto_hide = False
        Thread(target=self.animation.start, daemon=True).start()

        # Wait until Tkinter root is ready
        def wait_until_ready():
            while self.animation.root is None:
                time.sleep(0.05)
        Thread(target=wait_until_ready, daemon=True).start()
        # animation_thread.start()
        
        # Wait for animation to initialize
        # time.sleep(0.5)

        # time.sleep(0.5)
    
        try:
            # Simulate JARVIS usage
            print("JARVIS activated")
            self.animation.show()  # Show animation

        except KeyboardInterrupt:
            self.animation.stop()
    
    def shutdown(self):
        if self.animation:
            self.animation.stop()


    def query_local_phi(self, prompt):
        logging.info("Querying local Phi model...")
        response = self.local_ai.query_model(prompt)
        if response:
            # self.speak("Here's what I found.")
            return response.strip()
        else:
            self.speak("Sorry, I couldn't get a response from the local model.")
            return None



    def speak(self, text, verbose=False):
        """Convert text to speech with Jarvis-like voice"""
        # For non-verbose mode, only speak essential messages
        if not verbose and text.startswith(("Waiting", "Moving", "Clicking", "Typing", "Pressing", "Executing:")):
            logging.info(f"Skipped speech: {text}")
            return

        logging.info(f"Jarvis: {text}")
        # self.animation.set_speaking(True)           # Start animation
        if self.animation:
            print("JARVIS is speaking...")
            self.animation.show()
            self.animation.set_speaking(True)  # Start speaking animation

        self.voice_engine.say(text)
        self.voice_engine.runAndWait()              # This blocks until speech ends
        self.animation.set_speaking(False)
        print("JARVIS now showing the animation...")
        self.animation.show()                       # Hide animation after speaking
        # logging.info("finished speaking the answer in speak function")
        # print("JARVIS finished speaking.")


    def capture_screenshot(self):
        """Capture screenshot and encode to base64"""
        logging.info("Capturing screenshot...")
        screenshot = ImageGrab.grab()
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        logging.info(f"Screenshot captured: {len(img_str)} bytes")
        return img_str, screenshot  # Return both base64 and actual image

    def verify_mouse_position(self, x, y, target_description):
        """Verify if mouse is positioned correctly before clicking"""
        logging.info("enter In verify_mouse_position function...")
        attempts = 0
        
        while attempts < self.max_verification_attempts:
            # Move mouse to coordinates
            pyautogui.moveTo(x, y, duration=0.5)
            time.sleep(0.5)  # Wait for mouse to settle
            
            # Take screenshot with mouse at position
            screenshot_base64, _ = self.capture_screenshot()
            
            # Ask Gemini to verify position
            verification_prompt = f"""
            I've moved my mouse to position ({x}, {y}) on my screen.
            I'm trying to click on "{target_description}".
            
            Based on the screenshot, is my mouse positioned correctly to click on the target?
            
            Format your response ONLY as a JSON object:
            {{
                "is_correct": true/false,
                "adjustment_needed": {{
                    "dx": 0,  # Pixels to move horizontally (positive = right, negative = left)
                    "dy": 0   # Pixels to move vertically (positive = down, negative = up)
                }},
                "reasoning": "Brief explanation of why adjustment is needed or not"
            }}
            
            If the position is correct, set both dx and dy to 0.
            If the position is not correct, provide the required adjustment.
            """
            
            verification_response = self.local_ai.ask_llava_about_screenshot(verification_prompt)
            # verification_response = self.query_gemini_with_image(verification_prompt, screenshot_base64)
            
            try:
                # Extract JSON
                json_start = verification_response.find("{")
                json_end = verification_response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    verification_result = json.loads(verification_response[json_start:json_end])
                else:
                    # logging.error(f"Failed to parse verification response: {verification_response}")
                    # Default to proceed with clicking
                    return True
                    
                is_correct = verification_result.get("is_correct", False)
                adjustment = verification_result.get("adjustment_needed", {"dx": 0, "dy": 0})
                dx = adjustment.get("dx", 0)
                dy = adjustment.get("dy", 0)
                
                logging.info(f"Position verification - Correct: {is_correct}, Adjustment: dx={dx}, dy={dy}")
                
                if is_correct:
                    return True
                
                # Apply adjustment
                new_x = x + dx
                new_y = y + dy
                
                # Check if the new coordinates are within the screen
                if 0 <= new_x <= self.screen_width and 0 <= new_y <= self.screen_height:
                    x, y = new_x, new_y
                    self.speak(f"Adjusting mouse position.", verbose=True)
                else:
                    logging.warning(f"Adjusted coordinates ({new_x}, {new_y}) out of screen bounds!")
                    # Use the closest valid coordinates
                    x = max(0, min(new_x, self.screen_width))
                    y = max(0, min(new_y, self.screen_height))
                
                attempts += 1
                    
            except json.JSONDecodeError as e:
                logging.error(f"JSON parsing error in verification: {e}")
                # Default to proceed with clicking
                return True
            except Exception as e:
                logging.error(f"Error during position verification: {e}")
                # Default to proceed with clicking
                return True
                
        # If we've exceeded maximum attempts, just click and hope for the best
        logging.warning(f"Max verification attempts reached, proceeding with position ({x}, {y})")
        return True

    def execute_mouse_action(self, x, y, action="click", target_description="the target"):
        logging.info("enter In execute_mouse_action function...")
        """Move mouse to coordinates, verify position, and perform action - with tab fallback"""
        logging.info(f"Mouse action: {action} at ({x}, {y}) on {target_description}")
        
        # Try tab navigation first
        self.speak(f"Trying to navigate to {target_description} using keyboard.", verbose=True)
        tab_successful = self.tab_navigate_to_element(target_description)
        
        if tab_successful:
            # If tab navigation worked, just press Enter or Space to activate the element
            logging.info(f"Tab navigation successful, activating {target_description}")
            if action == "click" or action == "doubleclick":
                pyautogui.press('enter')
                if action == "doubleclick":
                    time.sleep(0.1)
                    pyautogui.press('enter')
            elif action == "rightclick":
                pyautogui.press('applications')  # Menu key for context menu
            return True
        
        # Tab navigation failed, fall back to traditional method
        self.speak(f"Using mouse to reach {target_description}.", verbose=True)
        
        # Verify position before clicking
        position_verified = self.verify_mouse_position(x, y, target_description)
        
        if position_verified:
            if action == "click":
                logging.info("Clicking")
                self.speak(f"Clicking on {target_description}.", verbose=True)
                pyautogui.click()
            elif action == "doubleclick":
                logging.info("Double-clicking")
                self.speak(f"Double-clicking on {target_description}.", verbose=True)
                pyautogui.doubleClick()
            elif action == "rightclick":
                logging.info("Right-clicking")
                self.speak(f"Right-clicking on {target_description}.", verbose=True)
                pyautogui.rightClick()
            return True
        else:
            logging.error(f"Failed to verify position for {target_description}")
            self.speak(f"Unable to locate {target_description} accurately.")
            return False

    def query_gemini_with_image(self, prompt, image_base64):
        """Send prompt and image to Gemini API"""
        try:
            logging.info("Querying Gemini with image...")

            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Prepare image part
            image_part = {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": image_base64
                }
            }
            
            # Configure generation parameters
            generation_config = {
                "temperature": 0.2,  # Lower temperature for more deterministic responses
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
            
            # Configure safety settings
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
            ]
            
            # Generate content with text and image
            response = model.generate_content(
                contents=[{"parts": [{"text": prompt}, image_part]}],
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            raw_response = response.text
            logging.info(f"Gemini raw response: {raw_response[:200]}...")
            return raw_response
            
        except Exception as e:
            logging.error(f"Error with Gemini API: {e}")
            return f"Error communicating with Gemini API: {str(e)}"



    def tab_navigate_to_element(self, target_description, max_tabs=20):
        """Navigate to an element using Tab key instead of mouse coordinates"""
        logging.info(f"Tab navigating to {target_description}")
        self.speak(f"Navigating to {target_description} using keyboard.", verbose=True)
        
        # Take initial screenshot
        screenshot_base64, _ = self.capture_screenshot()
        
        # Check if target element is already focused
        focus_check_prompt = f"""
        Based on this screenshot, is the element "{target_description}" currently focused/selected?
        Look for visual focus indicators like borders, glows, dashed lines, or color changes.
        
        Format your response ONLY as a JSON object:
        {{
            "is_focused": true/false,
            "confidence": 75,  # 0-100 confidence level
            "visual_cue": "Description of what indicates focus, if any"
        }}
        
        NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
        """
        
        check_response = self.local_ai.ask_llava_about_screenshot(focus_check_prompt)
        
        try:
            json_start = check_response.find("{")
            json_end = check_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                focus_check = json.loads(check_response[json_start:json_end])
            else:
                focus_check = {"is_focused": False, "confidence": 0}
            
            is_focused = focus_check.get("is_focused", False)
            confidence = focus_check.get("confidence", 0)
            
            if is_focused and confidence > 70:
                logging.info(f"Element '{target_description}' already focused")
                return True
                
            # Element not focused, start tabbing
            tab_count = 0
            forward_direction = True
            
            while tab_count < max_tabs:
                # Press Tab to move focus
                if forward_direction:
                    pyautogui.press('tab')
                    logging.info("Pressed Tab")
                else:
                    pyautogui.hotkey('shift', 'tab')
                    logging.info("Pressed Shift+Tab")
                
                time.sleep(0.3)  # Wait for focus to update
                
                # Every 3 tabs, check if we've reached the target
                if tab_count % 3 == 2:
                    screenshot_base64, _ = self.capture_screenshot()
                    
                    focus_verify_prompt = f"""
                    Based on this screenshot, is the element "{target_description}" currently focused/selected?
                    Look for visual focus indicators like borders, glows, dashed lines, or color changes.
                    
                    Format your response ONLY as a JSON object:
                    {{
                        "is_focused": true/false,
                        "confidence": 75,  # 0-100 confidence level
                        "direction_hint": "forward" or "backward" or "unknown"  # If not found, which direction to keep searching
                    }}
                    
                    NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
                    """
                    
                    verify_response = self.local_ai.ask_llava_about_screenshot(focus_verify_prompt)
                    
                    try:
                        json_start = verify_response.find("{")
                        json_end = verify_response.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            verify_result = json.loads(verify_response[json_start:json_end])
                        else:
                            verify_result = {"is_focused": False, "confidence": 0, "direction_hint": "unknown"}
                        
                        is_focused = verify_result.get("is_focused", False)
                        confidence = verify_result.get("confidence", 0)
                        direction_hint = verify_result.get("direction_hint", "unknown")
                        
                        if is_focused and confidence > 70:
                            logging.info(f"Found and focused on '{target_description}' after {tab_count+1} tabs")
                            self.speak(f"Found {target_description}.", verbose=True)
                            return True
                            
                        # If not found, consider changing direction based on hint
                        if tab_count > 10 and direction_hint != "unknown":
                            if direction_hint == "backward" and forward_direction:
                                forward_direction = False
                                logging.info("Changing tab direction to backward")
                            elif direction_hint == "forward" and not forward_direction:
                                forward_direction = True
                                logging.info("Changing tab direction to forward")
                    
                    except json.JSONDecodeError:
                        logging.error("Failed to parse verification response")
                
                tab_count += 1
            
            # If we've tabbed max_tabs times and still haven't found the element
            logging.warning(f"Failed to focus on '{target_description}' after {max_tabs} tabs")
            self.speak(f"I couldn't navigate to {target_description} using the keyboard.")
            return False
            
        except json.JSONDecodeError:
            logging.error("Failed to parse focus check response")
            return False
        
    def predefined_open_browser(self, url=None):
        """Predefined steps to open default browser and optionally navigate to URL"""
        logging.info("enter In predefined_open_browser function...")
        logging.info(f"Opening browser with URL: {url}")
        self.speak("Opening browser")
        
        if url:
            # Use cmd to directly open URL in default browser
            cmd_command = f'start {url}'
            self.execute_cmd_command(cmd_command)
            return True
        else:
            # Open default browser via Windows search
            pyautogui.press('win')
            time.sleep(0.5)
            self.execute_keyboard_action("edge")  # Or "chrome", etc.
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(2)  # Wait for browser to open
            return True

    def search_youtube(self, query):
        """Predefined steps to search YouTube for a specific query"""
        logging.info(f"Original search input: {query}")
        # self.speak(f"Searching YouTube for {query}")

        # 🔹 Step 0: Refine the query using Gemini
        try:
            refine_prompt = f"""
            Improve this YouTube search phrase for better results.
            Output only JSON like this: {{"query": "Improved search query"}}.
            Do not explain anything else.

            User input: "{query}"
            """
            refined_response = self.query_gemini(refine_prompt)

            json_start = refined_response.find("{")
            json_end = refined_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                refined_json = json.loads(refined_response[json_start:json_end])
                query = refined_json.get("query", query)
                logging.info(f"Refined query: {query}")
            else:
                logging.warning("Failed to parse refined query JSON, using original.")
        except Exception as e:
            logging.error(f"Error refining query with Gemini: {e}")

        # Step 1: Get video list
        videos = self.web_manager.get_youtube_results_list(query)
        if not videos:
            self.speak("Sorry, I couldn't find any YouTube videos.")
            return False

        # Step 2: Create prompt for Gemini
        prompt = f"""
            These are the top YouTube videos for '{query}'. Which one should I play?
            Respond only in JSON format with the index of the best video.
            Format your response as a JSON object:
            {{"index": 0}}

            Here are the videos:
            """
        for i, video in enumerate(videos):
            prompt += f"{i}. {video['title']}\n"

        # Step 3: Ask Gemini and parse response
        try:
            response = self.query_gemini(prompt)
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                result_json = json.loads(response[json_start:json_end])
            else:
                result_json = {"index": 0}
            index = result_json.get("index", 0)
            if index < 0 or index >= len(videos):
                logging.warning("Index out of bounds, defaulting to 0")
                index = 0
        except Exception as e:
            logging.error(f"Failed to parse Gemini response: {e}")
            index = 0

        # Step 4: Get the video URL
        video_url = videos[index]["url"]

        # Step 5: Play the video
        # self.speak(f"Playing {videos[index]['title']}")
        self.speak(f"Playing {videos[index]['title'][:50]}")

        safe_query = query.replace(" ", "+")
        if platform.system() == "Windows":
            print(f"Opening YouTube search results for: {query}")
            os.system(f'start https://www.youtube.com/results?search_query={safe_query}')
            os.system(f'start {video_url}')
        elif platform.system() == "Darwin":  # macOS
            os.system(f'open https://www.youtube.com/results?search_query={safe_query}')
            os.system(f'open {video_url}')
        else:  # Linux
            os.system(f'xdg-open https://www.youtube.com/results?search_query={safe_query}')
            os.system(f'xdg-open {video_url}')
        time.sleep(3)

        return True


    # def search_youtube(self, query):
    #     """Search for a video on YouTube"""
    #     logging.info(f"Searching YouTube for: {query}")
    #     self.speak(f"Searching YouTube for {query}")
        
    #     # Format the query for URL
    #     formatted_query = query.replace(" ", "+")
        
    #     if platform.system() == "Windows":
    #         # Using cmd is more efficient than opening browser first
    #         os.system(f'start https://www.youtube.com/results?search_query={formatted_query}')
    #     elif platform.system() == "Darwin":  # macOS
    #         os.system(f'open https://www.youtube.com/results?search_query={formatted_query}')
    #     else:  # Linux
    #         os.system(f'xdg-open https://www.youtube.com/results?search_query={formatted_query}')
        
    #     time.sleep(2)  # Wait for browser to load
    #     return True
    


    def search_google(self, query):
        """Search for a query on Google"""
        logging.info(f"Searching Google for: {query}")
        self.speak(f"Searching Google for {query}")
        
        # Format the query for URL
        formatted_query = query.replace(" ", "+")
        
        if platform.system() == "Windows":
            os.system(f'start https://www.google.com/search?q={formatted_query}')
        elif platform.system() == "Darwin":  # macOS
            os.system(f'open https://www.google.com/search?q={formatted_query}')
        else:  # Linux
            os.system(f'xdg-open https://www.google.com/search?q={formatted_query}')
        
        time.sleep(2)  # Wait for browser to load
        return True

    def predefined_google_search(self, search_query):
        """Predefined steps to search Google for a specific query"""
        logging.info(f"Searching Google for: {search_query}")
        self.speak(f"Searching Google for {search_query}")
        
        # Format the query for URL
        formatted_query = search_query.replace(' ', '+')
        google_search_url = f'https://www.google.com/search?q={formatted_query}'
        
        # Open directly via cmd
        cmd_command = f'start {google_search_url}'
        self.execute_cmd_command(cmd_command)
        
        time.sleep(2)  # Wait for search results to load
        return True


    def query_gemini(self, prompt):
        """Send prompt to Gemini API without image"""
        try:
            logging.info("Querying Gemini without image...")
            # model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Configure generation parameters
            # generation_config = {
            #     "temperature": 0.2,  # Lower temperature for more deterministic responses
            #     "top_p": 0.9,
            #     "top_k": 40,
            #     "max_output_tokens": 8192,
            # }
            
            # # Configure safety settings
            # safety_settings = [
            #     {
            #         "category": "HARM_CATEGORY_HARASSMENT",
            #         "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            #     },
            #     {
            #         "category": "HARM_CATEGORY_HATE_SPEECH",
            #         "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            #     },
            #     {
            #         "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            #         "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            #     },
            #     {
            #         "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            #         "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            #     },
            # ]

            logging.info(f" -=> for the prompt: {prompt[:200]}...")
            
            # Include conversation history if enabled
            if self.maintain_context and len(self.conversation_history) > 0:
                prompt = f"Previous interactions:\n{self.conversation_history}\n\nCurrent request: {prompt}"
            
            # Generate content
            # response = model.generate_content(
            #     contents=[{"parts": [{"text": prompt}]}],
            #     generation_config=generation_config,
            #     safety_settings=safety_settings
            # )

            response = self.query_local_phi(prompt)
            # logging.info(f"Gemini response: {response}...")
            raw_response = response
            # logging.info(f"Gemini raw response: {raw_response[:200]}...")
            # logging.info(f"Local Phi3 response-=> {raw_response}")
            # logging.info(f"Gemini response-=> {raw_response}")
            
            # Update conversation history if enabled
            if self.maintain_context:
                self.conversation_history.append(f"User: {prompt}")
                self.conversation_history.append(f"Assistant: {raw_response}")
                # Keep only last 10 interactions to prevent context overflow
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
            
            return raw_response
            
        except Exception as e:
            logging.error(f"Error with Gemini API: {e}")
            return f"Error communicating with Gemini API: {str(e)}"
        
        # Predefined functions for common tasks
    def open_browser(self, browser="edge"):
        """Open the default or specified web browser"""
        logging.info(f"Opening browser: {browser}")
        self.speak(f"Opening {browser}")
        
        if browser.lower() == "edge":
            pyautogui.press('win')
            time.sleep(0.5)
            pyautogui.write("edge")
            time.sleep(0.5)
            pyautogui.press('enter')
        elif browser.lower() == "chrome":
            pyautogui.press('win')
            time.sleep(0.5)
            pyautogui.write("chrome")
            time.sleep(0.5)
            pyautogui.press('enter')
        elif browser.lower() == "firefox":
            pyautogui.press('win')
            time.sleep(0.5)
            pyautogui.write("firefox")
            time.sleep(0.5)
            pyautogui.press('enter')
        else:
            # Use default browser
            try:
                webbrowser.open("https://www.google.com")
            except:
                # Fall back to command line approach
                if platform.system() == "Windows":
                    subprocess.Popen("start www.google.com", shell=True)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.Popen("open https://www.google.com", shell=True)
                else:  # Linux
                    subprocess.Popen("xdg-open https://www.google.com", shell=True)
        
        time.sleep(2)  # Wait for browser to open
        return True
    
    def open_file_explorer(self, path=None):
        """Open file explorer at specified path or default location"""
        if path:
            logging.info(f"Opening file explorer at: {path}")
            self.speak(f"Opening file explorer at {path}")
        else:
            logging.info("Opening file explorer")
            self.speak("Opening file explorer")
        
        if platform.system() == "Windows":
            if path:
                os.system(f'explorer "{path}"')
            else:
                os.system('explorer')
        elif platform.system() == "Darwin":  # macOS
            if path:
                os.system(f'open "{path}"')
            else:
                os.system('open .')
        else:  # Linux
            if path:
                os.system(f'xdg-open "{path}"')
            else:
                os.system('xdg-open .')
        
        time.sleep(1)
        return True
    
    def check_weather(self, location="current location"):
        """Check weather for a location"""
        logging.info(f"Checking weather for: {location}")
        self.speak(f"Checking weather for {location}")
        
        # Format location for URL
        formatted_location = location.replace(" ", "+")
        
        if platform.system() == "Windows":
            os.system(f'start https://www.google.com/search?q=weather+{formatted_location}')
        elif platform.system() == "Darwin":  # macOS
            os.system(f'open https://www.google.com/search?q=weather+{formatted_location}')
        else:  # Linux
            os.system(f'xdg-open https://www.google.com/search?q=weather+{formatted_location}')
        
        time.sleep(2)
        return True
    
    def check_news(self, topic=None):
        """Check news for a topic or general news"""
        if topic:
            logging.info(f"Checking news about: {topic}")
            self.speak(f"Checking news about {topic}")
            
            # Format topic for URL
            formatted_topic = topic.replace(" ", "+")
            url = f"https://news.google.com/search?q={formatted_topic}"
        else:
            logging.info("Checking general news")
            self.speak("Checking general news")
            url = "https://news.google.com"
        
        if platform.system() == "Windows":
            os.system(f'start {url}')
        elif platform.system() == "Darwin":  # macOS
            os.system(f'open {url}')
        else:  # Linux
            os.system(f'xdg-open {url}')
        
        time.sleep(2)
        return True

    def keyboard_tab_navigation(self, target_element, app_name=None):
        """Navigate UI using tab key until target element is focused"""
        logging.info("enter In keyboard_tab_navigation function...")
        logging.info(f"Starting tab navigation to find: {target_element}")
        self.speak(f"Navigating to {target_element}")
        
        max_tabs = 30  # Safety limit to prevent infinite tabbing
        tab_count = 0
        found = False
        
        # First attempt - tab forward
        while tab_count < max_tabs and not found:
            # Take screenshot every few tabs to check progress
            if tab_count % 3 == 0 or tab_count == 0:
                screenshot = self.capture_screenshot()
                
                # Ask Gemini if the target element is focused
                focus_prompt = f"""
                Look at this screenshot.
                Is the element "{target_element}" currently focused? 
                Look for visual indicators of focus like:
                - Highlighted borders
                - Different color
                - Glow effect
                - Underline
                - Dashed outline
                
                Answer ONLY with a JSON object:
                {{
                    "focused": true/false,
                    "confidence": 0-100,
                    "visible_but_not_focused": true/false,
                    "recommendation": "tab_forward", "tab_backward", "use_shortcut", or "not_found"
                }}
                """
                
                focus_response = self.local_ai.ask_llava_about_screenshot(focus_prompt)
                
                # Extract JSON
                try:
                    json_start = focus_response.find("{")
                    json_end = focus_response.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        focus_info = json.loads(focus_response[json_start:json_end])
                    else:
                        focus_info = {"focused": False, "confidence": 0, "visible_but_not_focused": False, "recommendation": "tab_forward"}
                        
                    logging.info(f"Focus check result: {focus_info}")
                    
                    # Element found
                    if focus_info.get("focused", False) and focus_info.get("confidence", 0) > 70:
                        logging.info(f"Element found after {tab_count} tabs")
                        found = True
                        break
                    
                    # Element visible but not focused
                    if focus_info.get("visible_but_not_focused", False):
                        # Continue tabbing a bit more if element is visible but not focused
                        recommendation = focus_info.get("recommendation", "tab_forward")
                        if recommendation == "tab_backward":
                            pyautogui.hotkey('shift', 'tab')
                            logging.info("Tabbing backward")
                        else:
                            pyautogui.press('tab')
                            logging.info("Tabbing forward")
                    # Not visible
                    else:
                        pyautogui.press('tab')
                        logging.info("Tabbing forward")
                        
                except json.JSONDecodeError:
                    logging.error(f"Error parsing focus check response: {focus_response}")
                    pyautogui.press('tab')
                    logging.info("Tabbing forward (default)")
            else:
                # Just tab without checking
                pyautogui.press('tab')
                logging.info("Tabbing forward")
                
            tab_count += 1
            time.sleep(0.3)  # Slower tabbing to let UI update
        
        # If not found with forward tabbing, try backward tabbing
        if not found:
            logging.info("Forward tabbing didn't find the element, trying backward tabbing")
            
            # Reset tab count
            tab_count = 0
            
            while tab_count < max_tabs and not found:
                # Take screenshot every few tabs to check progress
                if tab_count % 3 == 0 or tab_count == 0:
                    # screenshot = self.capture_screenshot()
                    
                    # Ask Gemini if the target element is focused
                    focus_prompt = f"""
                    Look at this screenshot.
                    Is the element "{target_element}" currently focused? 
                    Look for visual indicators of focus like:
                    - Highlighted borders
                    - Different color
                    - Glow effect
                    - Underline
                    - Dashed outline
                    
                    Answer ONLY with a JSON object:
                    {{
                        "focused": true/false,
                        "confidence": 0-100,
                        "visible_but_not_focused": true/false,
                        "recommendation": "tab_forward", "tab_backward", "use_shortcut", or "not_found"
                    }}
                    """
                    
                    focus_response = self.local_ai.ask_llava_about_screenshot(focus_prompt)
                    
                    # Extract JSON
                    try:
                        json_start = focus_response.find("{")
                        json_end = focus_response.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            focus_info = json.loads(focus_response[json_start:json_end])
                        else:
                            focus_info = {"focused": False, "confidence": 0, "visible_but_not_focused": False, "recommendation": "tab_backward"}
                            
                        logging.info(f"Focus check result: {focus_info}")
                        
                        # Element found
                        if focus_info.get("focused", False) and focus_info.get("confidence", 0) > 70:
                            logging.info(f"Element found after {tab_count} backward tabs")
                            found = True
                            break
                            
                    except json.JSONDecodeError:
                        logging.error(f"Error parsing focus check response: {focus_response}")
                
                # Tab backward
                pyautogui.hotkey('shift', 'tab')
                logging.info("Tabbing backward")
                tab_count += 1
                time.sleep(0.3)  # Slower tabbing to let UI update
        
        # Report result
        if found:
            self.speak(f"Found {target_element}")
            return True
        else:
            self.speak(f"Could not find {target_element} by tabbing")
            return False

    def map_ui_elements(self, app_name):
        """Map UI elements of an application"""
        logging.info("enter In map_ui_elements function...")
        logging.info(f"Mapping UI elements for {app_name}")
        self.speak(f"Analyzing interface for {app_name}")
        
        screenshot = self.capture_screenshot()
        
        mapping_prompt = f"""
        Look at this screenshot of {app_name}.
        Analyze the interface and identify all clickable/interactive elements.
        For each element, determine its approximate tabbing order.
        
        Return ONLY a JSON array of UI elements with these properties:
        - label: The text or description of the element
        - tab_index: Estimated tab order index (1, 2, 3...)
        - type: Type of UI element (button, link, input, checkbox, etc.)
        
        Format:
        [
            {{"label": "Search", "tab_index": 1, "type": "input"}},
            {{"label": "Settings", "tab_index": 2, "type": "button"}},
            ...
        ]
        """
        
        mapping_response = self.local_ai.ask_llava_about_screenshot(mapping_prompt)
        
        try:
            # Extract JSON array
            array_start = mapping_response.find("[")
            array_end = mapping_response.rfind("]") + 1
            if array_start >= 0 and array_end > array_start:
                ui_map = json.loads(mapping_response[array_start:array_end])
                
                # Store the UI map
                self.ui_element_maps[app_name] = ui_map
                
                logging.info(f"UI mapping successful for {app_name}: {len(ui_map)} elements mapped")
                return ui_map
            else:
                logging.error(f"Failed to parse UI mapping response: {mapping_response}")
                return []
                
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error for UI mapping: {e}")
            logging.error(f"Mapping response: {mapping_response}")
            return []


    def execute_keyboard_action(self, text):
        """Type text using keyboard"""
        logging.info(f"Typing: {text}")
        self.speak(f"Typing: {text}", verbose=True)
        pyautogui.typewrite(text, interval=0.05)

    def execute_keyboard_shortcut(self, keys):
        """Execute keyboard shortcut"""
        logging.info(f"Pressing {keys}")
        self.speak(f"Pressing {keys}", verbose=True)

        # Decide between hotkey and press
        if '+' in keys:
            keys_list = keys.split('+')
            pyautogui.hotkey(*[k.strip() for k in keys_list])
        else:
            pyautogui.press(keys.strip())



    def open_app(self, app_name):
        """Open an application using Windows search"""
        logging.info(f"Opening {app_name}")
        self.speak(f"Opening {app_name}")
        # Press Windows key
        pyautogui.press('win')
        time.sleep(0.5)
        # Type app name
        pyautogui.typewrite(app_name)
        time.sleep(1)
        # Press Enter to open
        pyautogui.press('enter')
        time.sleep(2)  # Wait for app to open

    def execute_cmd_command(self, command):
        """Execute command in Command Prompt"""
        logging.info(f"Executing command: {command}")
        self.speak(f"Executing command")
        
        # Open Command Prompt if not already open
        self.open_app("cmd")
        # Type and execute command
        pyautogui.typewrite(command)
        pyautogui.press('enter')
        time.sleep(1)  # Wait for command to execute
        
        # Verify command execution
        return self.verify_step_completion("verify if command executed successfully")
    
    def verify_step_completion(self, step_description):
        """Verify if a step was completed successfully using screenshots"""
        logging.info("enter In verify_step_completion function...")
        logging.info(f"Verifying completion of: {step_description}")
        
        # Take screenshot
        # screenshot = self.capture_screenshot()
        
        # Ask Gemini if the step was completed
        verification_prompt = f"""
        Look at this screenshot and verify:
        "{step_description}"
        
        Answer ONLY with a JSON object:
        {{
            "completed": true/false,
            "confidence": 0-100,
            "reason": "brief explanation of your assessment",
            "suggestion": "what to try if not completed successfully (only if needed)"
        }}
        """
        
        # verification_response = self.local_ai.ask_llava_about_screenshot(verification_prompt, screenshot)
        
        # try:
        #     # Extract JSON
        #     json_start = verification_response.find("{")
        #     json_end = verification_response.rfind("}") + 1
        #     if json_start >= 0 and json_end > json_start:
        #         verification_result = json.loads(verification_response[json_start:json_end])
        #     else:
        #         logging.error(f"Failed to parse verification response: {verification_response}")
        #         return False
                
        #     completed = verification_result.get("completed", False)
        #     confidence = verification_result.get("confidence", 0)
        #     reason = verification_result.get("reason", "No reason provided")
        #     suggestion = verification_result.get("suggestion", "")
            
        #     logging.info(f"Step verification result: {completed} (confidence: {confidence})")
        #     logging.info(f"Reason: {reason}")
            
        #     if completed and confidence > 70:
        #         return True
        #     else:
        #         if suggestion:
        #             logging.info(f"Suggestion: {suggestion}")
        #             self.speak("Let me try a different approach.")
        #         return False
                
        # except json.JSONDecodeError as e:
        #     logging.error(f"JSON parsing error for verification: {e}")
        #     logging.error(f"Verification response: {verification_response}")
        #     return False
    
    def process_command(self, user_command):
        """Process user command - determine if it's a question, task, or special command"""
        logging.info("enter In process_command function...")
        # Check for special commands first
        if "set alarm" in user_command.lower():
            logging.info("Processing alarm command...")
            # Extract time
            time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', user_command.lower())
            if time_match:
                hour = time_match.group(1)
                minute = time_match.group(2) or "00"
                time_string = f"{hour}:{minute}"
                return self.task_manager.set_alarm(time_string)
        
        elif "set timer" in user_command.lower() or "set a timer" in user_command.lower():
            logging.info("Processing timer command...")
            # Extract time
            # time_match = re.search(r'(\d+)\s*(seconds?|minutes?|hours?)', user_command.lower())
            # if time_match:
            #     duration = time_match.group(1)
            #     unit = time_match.group(2)
            #     return self.task_manager.set_timer(duration, unit)
            self.search_google(user_command)
            return


        elif "send message to" in user_command.lower() or "send whatsapp to" in user_command.lower():
            logging.info("Processing WhatsApp message command...")
            # Extract contact and message
            contact_match = re.search(r'send (?:message|whatsapp) to (\w+)', user_command.lower())
            message_match = re.search(r'saying (.*)', user_command.lower())
            
            if contact_match and message_match:
                contact = contact_match.group(1)
                message = message_match.group(1)
                return self.task_manager.send_whatsapp_message(contact, message)
        
        elif "read the screen" in user_command.lower() or "what's on screen" in user_command.lower():
            logging.info("Processing screen reading command...")
            return self.task_manager.read_screen_content()
        
        elif "search perplexity" in user_command.lower() or "ask perplexity" in user_command.lower() or "perplexity" in user_command.lower() or "complexity" in user_command.lower() or "ask model" in user_command.lower():
            logging.info("Processing Perplexity search command...")
            query = user_command.lower().replace("search perplexity for", "").replace("search perplexity", "").replace("ask model","").strip()
            return self.task_manager.search_ai_and_report(query, "perplexity")
        
        elif "search chatgpt" in user_command.lower() or "ask chatgpt" in user_command.lower():
            logging.info("Processing ChatGPT search command...")
            query = user_command.lower().replace("search chatgpt for", "").replace("search chatgpt", "").strip()
            return self.task_manager.search_ai_and_report(query, "chatgpt")
        
        elif "read my emails" in user_command.lower() or "check gmail" in user_command.lower():
            logging.info("Processing email reading command...")
            return self.task_manager.read_email_from_gmail()
        
        
        elif "play" in user_command.lower() or "youtube" in user_command.lower():
            logging.info("Processing YouTube search command...")
            return self.search_youtube(user_command)
        
        elif "open" in user_command.lower() or "launch" in user_command.lower():
            # Extract app name
            logging.info("Processing open command...")
            app_match = re.search(r'open (.+)', user_command.lower())
            if app_match:
                app_name = app_match.group(1)
                return self.open_app(app_name)
            
        # If no special command matched, continue with standard classification
        classification_prompt = f"""
            Analyze the following user input carefully:

            "{user_command}"

            Your task is to classify it into one of the following **precise categories**, based on its intent:

            1. **"conversational_question"** – Any question or statement that:
               - Asks about the AI's opinions, feelings, or state (e.g., "How are you?", "What's your favorite color?")
               - Seeks a casual chat or engagement (e.g., "Tell me a joke", "Let's talk")
               - Asks for subjective views or preferences (e.g., "What do you think about space travel?")
               - Greetings or small talk (e.g., "Good morning", "How's it going?")
               - Personal questions directed at the AI (e.g., "Do you like music?")
               - Philosophical or hypothetical discussions without factual answers

            2. **"factual_question"** – A question that requires specific factual information such as:
               - Current data points (e.g., weather, time, dates)
               - Verifiable facts about the world (e.g., "How tall is Mount Everest?")
               - Current events and news (e.g., "Who won yesterday's election?")
               - Historical information (e.g., "When was the moon landing?")
               - Definitions of concepts (e.g., "What is photosynthesis?")
               - NOTE: Questions about the AI's state like "How are you?" are NOT factual questions

            3. **"task"** – A command or instruction asking the assistant to perform an operation such as:
               - Opening or interacting with applications (e.g., "Open Chrome", "Launch Spotify")
               - System controls (e.g., "Turn on WiFi", "Increase volume")
               - Taking actions on behalf of the user (e.g., "Send an email", "Take a screenshot")
               - Device manipulation (e.g., "Type this message", "Click on that button")

            4. **"search_chatgpt"** – Questions related to:
               - Programming and coding (e.g., "How to create a Python class?")
               - Technical concepts explanation (e.g., "What is an API?", "Explain blockchain")
               - Code review or debugging (e.g., "Fix this JavaScript function")
               - Computer science concepts (e.g., "How does garbage collection work?")

            5. **"research_question"** – Complex questions requiring in-depth research such as:
               - Multi-faceted topics (e.g., "What causes inflation?")
               - Topics requiring synthesis of multiple sources (e.g., "How do vaccines work?")
               - Current state of evolving fields (e.g., "What is the future of renewable energy?")
               - Questions requiring comprehensive analysis (e.g., "Why is climate change accelerating?")
               - Questions where the answer would benefit from multiple perspectives or sources
            ---

            **Format your response in this strict JSON structure:**

            {{
                "type": "<one of: conversational_question, factual_question, task, search_chatgpt, research_question>",
                "reasoning": "Brief explanation of why this classification fits",
                "formatted_question": "Rephrase the user's input into a clear, professional question or command. This should be in natural language and suitable for search or answering. Do not include this instruction or repeat the input.If could not understand the input, just repeat the input as it is.",'",
            }}

            CRITICAL REMINDERS:
            - "How are you?" and similar questions about the AI's state are ALWAYS "conversational_question"
            - Questions about preferences, feelings, or opinions are ALWAYS "conversational_question"
            - Only classify as "factual_question" if it requires real-world data or verifiable facts
            - Do not include anything outside the JSON response
            """


        
        classification_response = self.query_gemini(classification_prompt)
        
        try:
            # Extract JSON
            json_start = classification_response.find("{")
            json_end = classification_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                classification = json.loads(classification_response[json_start:json_end])
            else:
                classification = {"type": "factual_question", "reasoning": "Default to task"}
                
            input_type = classification.get("type", "task")
            formatted_question = classification.get("formatted_question", user_command)
            logging.info(f"Input classified as: {input_type}")
            
            # Process based on type
            if input_type == "conversational_question":
                self.answer_question(user_command)
            elif input_type == "factual_question":
                self.scrape_ai(formatted_question)
                # self.web_manager.search_perplexity(user_command)
            elif input_type == "research_question":
                self.ask_perplexity(formatted_question)
            elif input_type == "search_chatgpt":
                self.web_manager.search_chatgpt(formatted_question)
            elif input_type == "task":
                self.speak(f"I'll assist you.")
                self.execute_step_by_step_task(formatted_question)
            else:
                self.search_google(formatted_question)
                
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {e}")
            # Default to task processing
            # self.execute_step_by_step_task(user_command)
            self.ask_perplexity(user_command)

    def answer_question(self, question):
        """Answer a question without performing actions"""
        answer_prompt = f"""
        Please answer this question:
        "{question}"
            
        Provide a concise and informative answer as if you are a cool and smart voice assistant like Jarvis.
        Keep the answer natural, conversational and helpful. Answer should be like, given by a cool Jarvis AI Assistant, no other explanations required, and keep it little bit short and sweet.
        **Format your response in this strict JSON structure:**

            {{
                "answer": "<your answer here>"
                }}
        """
        logging.info(f"Answering question: {question}")
        answer = self.query_gemini(answer_prompt)
        logging.info(f"Answer: {answer}")
        try:
            # Extract JSON
            json_start = answer.find("{")
            json_end = answer.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                response = json.loads(answer[json_start:json_end])
            else:
                response = {"answer": "sorry, no answer found"}

            answer = response.get("answer", "Sorry, I couldn't find an answer.")    

            logging.info(f"now calling our speak function for answering the question:::::::::::::::{answer}")
            self.speak(answer)
            logging.info("finished speaking the answer in answer_question function")
            return

        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {e}")
            # Default to task processing
            self.search_google(question)
            



    def scrape_ai(self, question):
        """Scrape AI for a factual question using self.local_ai and self.scrape"""
        logging.info(f"Scraping AI for: {question}")
        
        # Maximum number of scraping attempts before falling back to Perplexity
        max_attempts = 2
        current_attempt = 0
        
        while current_attempt < max_attempts:
            current_attempt += 1
            logging.info(f"Scraping attempt #{current_attempt}")
            
           
            prompt = (
                f"You are a precise research assistant. Based on the question: '{question}', "
                "choose the **best single website URL** to get the accurate information from, "
                "using ONLY the following list of reliable sources.\n\n"

                "IMPORTANT INSTRUCTIONS FOR URL SELECTION:\n"
                "1. For time, weather, or current conditions questions, use the HOMEPAGE of weather sites\n"
                "2. For general knowledge, use specific Wikipedia article pages when possible\n"
                "3. For programming questions, use specific documentation pages\n"
                "4. For health questions, prioritize .gov sites like CDC or WHO\n"
                "5. For recent news, use news site homepages unless about specific events\n"
                "6. Always select the MOST SPECIFIC URL that will directly answer the question\n"
                "7. If unsure about the specific URL structure, use the domain homepage\n\n"

                "**General Knowledge & Encyclopedias**:\n"
                "- https://en.wikipedia.org (use specific article URLs like /wiki/Topic_Name)\n"
                "- https://www.britannica.com (use specific articles like /topic/specific-topic)\n"
                "- https://www.imdb.com (for movies/shows use /title/tt[ID] format)\n"

                "**Time & Weather**:\n"
                "- https://www.accuweather.com (use homepage for current time/conditions, or /en/[country]/[region]/[city] for specific locations)\n"
                "- https://weather.com (use homepage or /weather/today/l/[location_code] for specific forecasts)\n"
                "- https://www.timeanddate.com (use /worldclock/ for current time questions)\n"

                "**News**:\n"
                "- https://www.bbc.com/news (use homepage for recent news, specific sections like /world, /business for topical news)\n"
                "- https://www.reuters.com (use /world or /business sections for specific topics)\n"
                "- https://www.nytimes.com (use sections like /section/world or /section/technology for specific topics)\n"
                "- https://edition.cnn.com (use homepage for breaking news)\n"
                "- https://www.aljazeera.com (use /news for general news)\n"
                "- https://www.theguardian.com (use sections like /world, /technology, etc.)\n"

                "**Science & Research**:\n"
                "- https://www.sciencedaily.com (use /releases for recent discoveries)\n"
                "- https://www.nature.com (use /subjects/[topic] for specific scientific topics)\n"
                "- https://www.nationalgeographic.com (use /science, /environment, etc. sections)\n"
                "- https://www.scientificamerican.com (use /topics/[specific-topic] for targeted info)\n"

                "**Technology & Programming**:\n"
                "- https://developer.mozilla.org (use /en-US/docs/Web/[specific_tech] for web development)\n"
                "- https://docs.python.org (use /3/ for Python 3 documentation, with specific pages like /library/[module].html)\n"
                "- https://stackoverflow.com (use /questions/tagged/[tag] for specific programming topics)\n"
                "- https://www.geeksforgeeks.org (use /[language]/[specific-topic] for programming tutorials)\n"
                "- https://www.w3schools.com (use /[technology]/[specific_topic].asp for tutorials)\n"
                "- https://www.cnet.com (use /news/[topic] for tech news, reviews/[product-category] for reviews)\n"
                "- https://techcrunch.com (use homepage for latest tech news)\n"

                "**Finance & Economy**:\n"
                "- https://www.investopedia.com (use /terms/[term] for financial term definitions)\n"
                "- https://www.bloomberg.com (use /markets for market data)\n"
                "- https://www.forbes.com (use /money, /business, etc. for specific topics)\n"
                "- https://www.marketwatch.com (use homepage for latest market data)\n"

                "**Health & Medicine**:\n"
                "- https://www.cdc.gov (use /[disease-name]/index.html for specific conditions)\n"
                "- https://www.who.int (use /health-topics/[topic] for global health issues)\n"
                "- https://www.mayoclinic.org (use /diseases-conditions/[condition]/symptoms-causes/syc-[ID] for specific conditions)\n"
                "- https://www.healthline.com (use /health/[condition] for health topics)\n"
                "- https://www.webmd.com (use /[condition]/default.htm for medical conditions)\n"

                "**Education & Learning**:\n"
                "- https://www.khanacademy.org (use /[subject]/[topic] for educational content)\n"
                "- https://ocw.mit.edu (use /courses/[department]/[course-number] for course materials)\n"
                "- https://www.coursera.org (use /learn/[course-name] for specific courses)\n"
                "- https://www.edx.org (use /course/[course-name] for specific courses)\n\n"

                "EXAMPLES OF GOOD URL SELECTION:\n"
                "- Question: 'What is the current time?' → {\"website\": \"https://www.timeanddate.com/worldclock/\"}\n"
                "- Question: 'What's the weather in New York?' → {\"website\": \"https://weather.com/weather/today/l/New+York+NY\"}\n"
                "- Question: 'Who is Albert Einstein?' → {\"website\": \"https://en.wikipedia.org/wiki/Albert_Einstein\"}\n"
                "- Question: 'How to use Python list comprehension?' → {\"website\": \"https://docs.python.org/3/tutorial/datastructures.html#list-comprehensions\"}\n"
                "- Question: 'What are symptoms of COVID-19?' → {\"website\": \"https://www.cdc.gov/coronavirus/2019-ncov/symptoms-testing/symptoms.html\"}\n"
                "- Question: 'Latest tech news' → {\"website\": \"https://techcrunch.com\"}\n\n"

                "Return ONLY a JSON object with the best website URL:\n"
                "{\n  \"website\": \"https://example.com/specific-page-if-needed\"\n}\n"
                "DO NOT explain your reasoning. Just return the JSON object."
            )

            try:
                ai_response = self.local_ai.query_model(prompt)
                ai_response_json = extract_json_block(ai_response)
                response_json = json.loads(ai_response_json)
                url = response_json.get("website")
                
                if not url:
                    logging.warning(f"No URL received in attempt #{current_attempt}")
                    continue  # Try next iteration if available
                    
                logging.info(f"Got URL: {url} in attempt #{current_attempt}")
                
                # 2. Scrape the website
                scraped_data = self.web_manager.scrape(url)
                if not scraped_data:
                    logging.warning(f"No data scraped from {url} in attempt #{current_attempt}")
                    continue  # Try next iteration if available
                    
                # 3. Check relevance of scraped data
                logging.info(f"Checking relevance of scraped data (attempt #{current_attempt})")
                
                relevance_prompt = (
                    "You are verifying the relevance of data extracted from a website.\n\n"
                    f"**User Question**:\n{question}\n\n"
                    f"**Scraped Data**:\n{scraped_data[:1500]}\n\n"
                    "Is the scraped content a relevant and direct answer to the question?\n\n"
                    "Reply with Yes if the small or big part of the scraped content contains th answer for User question?\n\n"
                    "⚠️ Only reply with a single JSON object in this format:\n"
                    "{\n  \"relevant\": \"yes\"\n}\n\n"
                    "Use \"yes\" or \"no\". Do not include explanations or comments."
                )

                relevance_response = self.local_ai.query_model(relevance_prompt)
                relevance_json = json.loads(extract_json_block(relevance_response))
                
                if relevance_json.get("relevant", "").strip().lower() == "yes":
                    logging.info(f"Scraped data is relevant in attempt #{current_attempt}. Proceeding to summarize.")
                    
                    summary_prompt = (
                        "You are a smart summarizer.\n\n"
                        f"**User Question**:\n{question}\n\n"
                        f"**Scraped Data**:\n{scraped_data[:4000]}\n\n"
                        "Based on the type of question, either give a short direct answer, a bulleted summary, or a paragraph summary — "
                        "choose what fits best to convey the answer clearly. Just respond with the summary, nothing else."
                    )

                    summary = self.local_ai.query_model(summary_prompt)
                    # Remove thinking tags from DeepSeek R1 model output
                    clean_summary = self.remove_thinking_tags(summary)
                    self.speak(clean_summary)
                    return  # Successfully found relevant information, exit function
                else:
                    logging.info(f"Scraped content was not relevant in attempt #{current_attempt}")
                    # We'll continue the loop to try another source
            
            except Exception as e:
                logging.exception(f"Error in scraping attempt #{current_attempt}: {str(e)}")
                # Continue to next attempt if available
        
        # If we reach here, all attempts failed - fall back to Perplexity
        logging.info("All scraping attempts failed. Falling back to Perplexity.")
        # perplexity_response = self.ask_perplexity(question)
        perplexity_response = self.web_manager.search_perplexity(question)
        # Remove thinking tags from the Perplexity response as well

        summary_prompt = (
            "You are a smart summarizer assistant.\n\n"
            f"**User Question**:\n{question}\n\n"
            f"**Scraped Data**:\n{perplexity_response[:4000]}\n\n"
            "👉 Using only the information in the scraped data above, generate the best possible answer to the user's question.\n"
            "Choose the most suitable format based on the question type — a direct short answer, a bullet list, or a paragraph summary.\n"
            "Do NOT restate the question. Do NOT add any extra explanations or context.\n"
            "Just respond with the answer, in the best format to convey it clearly."
        ) 

        summary = self.local_ai.query_model(summary_prompt)
        # Remove thinking tags from DeepSeek R1 model output
        clean_summary = self.remove_thinking_tags(summary)
        self.speak(clean_summary)
        # return  # Successfully found relevant information, exit function

        # clean_response = self.remove_thinking_tags(perplexity_response)
        # self.speak(clean_response)

        

    def ask_perplexity(self, question):
        """Ask a factual question to Perplexity AI"""
        logging.info(f"Asking Perplexity: {question}")
        self.speak(f"Searching for {question} on Perplexity")
        
        # Format the query for URL
        formatted_query = question.replace(" ", "+")
        
        if platform.system() == "Windows":
            os.system(f'start https://www.perplexity.ai/search?q={formatted_query}')
        elif platform.system() == "Darwin":  # macOS
            os.system(f'open https://www.perplexity.ai/search?q={formatted_query}')
        else:  # Linux
            os.system(f'xdg-open https://www.perplexity.ai/search?q={formatted_query}')
        
        time.sleep(2)  # Wait for browser to load
        
        return True
    
    def ask_chatgpt(self, question):
        """Ask a technical question to ChatGPT"""
        logging.info(f"Asking ChatGPT: {question}")
        self.speak(f"Searching for {question} on ChatGPT")
        
        # Format the query for URL
        formatted_query = question.replace(" ", "+")
        
        if platform.system() == "Windows":
            os.system(f'start https://chat.openai.com/search?q={formatted_query}')
        elif platform.system() == "Darwin":
            os.system(f'open https://chat.openai.com/search?q={formatted_query}')
        else:  # Linux
            os.system(f'xdg-open https://chat.openai.com/search?q={formatted_query}')
        
        time.sleep(2)  # Wait for browser to load

        return True
    

    def verify_action_with_ui_elements(self, expected_element=None, expected_text=None):
        logging.info("enter In verify_action_with_ui_elements function...")
        """Verify action success by checking for UI elements or text on screen"""
        try:
            time.sleep(1)  # Give UI time to update
            
            if expected_element:
                element = self.ui_manager.find_element_by_name(expected_element)
                if element and element.Exists():
                    logging.info(f"Verification successful: Found element '{expected_element}'")
                    return True
            
            if expected_text:
                screen_text = self.ui_manager.get_window_text()
                if expected_text.lower() in screen_text.lower():
                    logging.info(f"Verification successful: Found text '{expected_text}'")
                    return True
                    
            # If neither check passed
            logging.warning("Verification failed: Expected elements not found")
            return False
        except Exception as e:
            logging.error(f"Error during UI verification: {e}")
            return False

    def smart_action_retry(self, action_func, action_args=None, max_attempts=3, verify_func=None, verify_args=None):
        """Smart retry mechanism for actions with verification"""
        logging.info("enter In smart_action_retry function...")
        if action_args is None:
            action_args = []
        if verify_args is None:
            verify_args = []
            
        attempt = 0
        success = False
        
        while attempt < max_attempts and not success:
            attempt += 1
            logging.info(f"Attempt {attempt} of {max_attempts}")
            
            try:
                # Execute action
                if action_args:
                    action_func(*action_args)
                else:
                    action_func()
                    
                # Verify if function provided
                if verify_func:
                    time.sleep(1)  # Wait for UI to update
                    if verify_args:
                        success = verify_func(*verify_args)
                    else:
                        success = verify_func()
                else:
                    # If no verification function, assume success
                    success = True
                    
                if success:
                    logging.info("Action executed successfully")
                    return True
                else:
                    logging.warning(f"Action verification failed on attempt {attempt}")
                    
                    # If this wasn't the last attempt, try to recover
                    if attempt < max_attempts:
                        logging.info("Attempting recovery...")
                        # Press Escape to close any dialogs
                        pyautogui.press('escape')
                        time.sleep(1)
            except Exception as e:
                logging.error(f"Error during action: {e}")
                
        # If we get here, all attempts failed
        logging.error(f"Action failed after {max_attempts} attempts")
        return False

    def execute_step_by_step_task(self, user_command):
        """Execute a task using step-by-step approach with verification"""
        """Execute a task using multi-modal approach"""
        logging.info(f"Entered in execute_step_by_step_task, Executing task: {user_command}")
        
        # Check if this is a common task that can use predefined function
        common_task_prompt = f"""
        You are a smart assistant responsible for classifying user commands into predefined tasks.

        Analyze the following user command carefully:
        "{user_command}"

        Your job is to:
        1. Identify if this command matches any **common task** from the list below.
        2. If yes, select the appropriate `task_type` and extract any necessary parameters (such as a query or location).
        3. If the command is general (like asking the current time, date, or simple facts), and cannot be performed locally, treat it as a **Google search** using `search_google`.

        Common task types:
        - "search_youtube": Find a video or song on YouTube (e.g., "Play Anuv Jain on YouTube")
        - "search_google": Search Google for facts, information, or simple questions (e.g., "What’s the capital of France?" or "current time in Tokyo")
        - "open_file_explorer": Open a specific folder (e.g., "Open Downloads folder")
        - "check_weather": Get the current weather or forecast (e.g., "What's the weather in Delhi?")
        - "check_news": Fetch the latest news about a topic (e.g., "Give me news about AI")
        - "open_browser": Launch a web browser (e.g., "Open Chrome")
        - "open_app": Open a specific application (e.g., "Open Notepad")
        - "open_command_prompt": Open Command Prompt or Terminal (e.g., "Open Command Prompt")
        - "open_settings": Open system settings (e.g., "Open Windows Settings")
        

        Expected JSON response format:
        {{
        "matches_common_task": true or false,
        "task_type": "search_youtube" | "search_google" | "open_file_explorer" | "check_weather" | "check_news" | "open_browser" | null,
        "parameters": {{
            "query": "...",      # For search tasks
        }}
        }}

        Respond **only** with a valid JSON object — no explanation or additional text.
        """

        
        common_task_response = self.query_gemini(common_task_prompt)
        
        try:
            # Extract JSON
            json_start = common_task_response.find("{")
            json_end = common_task_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                common_task_info = json.loads(common_task_response[json_start:json_end])
            else:
                common_task_info = {"matches_common_task": False}
                
            matches_common_task = common_task_info.get("matches_common_task", False)
            
            if matches_common_task:
                task_type = common_task_info.get("task_type")
                parameters = common_task_info.get("parameters", {})
                
                logging.info(f"Executing common task: {task_type} with parameters: {parameters}")
                
                # Execute the predefined function
                if task_type in self.common_tasks:
                    if parameters:
                        self.common_tasks[task_type](**parameters)
                    else:
                        self.common_tasks[task_type]()
                    return
            
            # If not a common task, determine the best approach
            approach_prompt = f"""
            I need to execute this task on a {self.system_info["platform"]} computer: "{user_command}"
            
            Based on this request, tell me which approach would be best:
            1. Using Command Prompt commands
            2. Using keyboard shortcuts
            3. A combination of the above
            
            Format your response ONLY as a JSON object with these fields:
            {{
                "approach": "cmd" or "tab_navigation" or "shortcut" or "combined",
                "reasoning": "Brief explanation of why this approach is best"
            }}
            """
            # 3. Using keyboard navigation with tab key
            
            approach_response = self.query_gemini(approach_prompt)
            
            # Extract JSON
            json_start = approach_response.find("{")
            json_end = approach_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                approach_json = json.loads(approach_response[json_start:json_end])
            else:
                approach_json = {"approach": "combined", "reasoning": "Defaulting to combined approach"}
                
            approach = approach_json.get("approach", "combined")
            logging.info(f"Selected approach: {approach}")
            logging.info(f"Reasoning: {approach_json.get('reasoning', 'No reasoning provided')}")
            
            # Based on approach, execute the appropriate method
            if approach == "cmd":
                self.execute_cmd_approach(user_command)
            elif approach == "tab_navigation":
                self.execute_tab_navigation_approach(user_command)
            elif approach == "shortcut":
                self.execute_shortcut_approach(user_command)
            else:  # combined or default
                self.execute_combined_approach(user_command)
                
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {e}")
            logging.error(f"Approach response: {common_task_response}")
            # Default to combined approach if parsing fails
            # self.execute_combined_approach(user_command)
        except Exception as e:
            logging.error(f"Error determining approach: {e}")
            # Default to combined approach
            self.execute_combined_approach(user_command)

    def execute_cmd_approach(self, user_command):
        logging.info("enter In execute_cmd_approach function...")
        """Execute using Command Prompt approach"""
        cmd_prompt = f"""
        I need to execute this task on a {self.system_info["platform"]} computer: "{user_command}"
        
        Please provide ONLY the exact Command Prompt (CMD) commands I need to run.
        Prioritize using PowerShell or Command Prompt commands over opening applications with GUI.
        
        Format your response ONLY as a JSON array of command strings, like this:
        ["command1", "command2", "command3"]
        
        NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
        """
        
        cmd_response = self.query_gemini(cmd_prompt)
        
        try:
            # Extract JSON array
            array_start = cmd_response.find("[")
            array_end = cmd_response.rfind("]") + 1
            if array_start >= 0 and array_end > array_start:
                commands = json.loads(cmd_response[array_start:array_end])
            else:
                self.speak("I couldn't parse the command response properly.")
                logging.error(f"Failed to parse CMD response: {cmd_response}")
                return
                
            # Execute each command
            # Open Command Prompt once
            self.open_app("cmd")
            time.sleep(1)
            
            for cmd in commands:
                logging.info(f"Executing: {cmd}")
                pyautogui.typewrite(cmd)
                pyautogui.press('enter')
                time.sleep(2)  # Wait between commands
                
                # Verify command execution
                if not self.verify_step_completion(f"Verify if command '{cmd}' executed successfully"):
                    self.speak("I encountered an issue with the command. Let me try a different approach.")
                    return self.execute_combined_approach(user_command)
                
            self.speak("Task complete.")
                
        except json.JSONDecodeError as e:
            self.speak("I couldn't parse the command response properly.")
            logging.error(f"JSON parsing error: {e}")
            logging.error(f"Command response: {cmd_response}")
        except Exception as e:
            self.speak("I encountered an issue executing the commands.")
            logging.error(f"Error executing commands: {e}")

    def execute_tab_navigation_approach(self, user_command):
        logging.info("enter In execute_tab_navigation_approach function...")
        """Execute using tab navigation approach"""
        # Take initial screenshot
        screenshot = self.capture_screenshot()
        
        logging.info("Analyzing screen for tab navigation...")
        
        # Send screenshot to Gemini for analysis
        tab_nav_prompt = f"""
        I need to execute this task on a {self.system_info["platform"]} computer: "{user_command}"
        
        I'm sending you a screenshot of my current screen. I want to use keyboard tab navigation instead of mouse clicks.
        
        Format your response ONLY as a JSON array of action objects:
        [
            {{"type": "open_app", "app": "chrome"}},
            {{"type": "focus_element", "element": "Search bar", "description": "Main search input field at top"}},
            {{"type": "type", "text": "example search"}},
            {{"type": "shortcut", "keys": "enter"}}
        ]
        
        For "focus_element" actions, provide a clear description of what the element looks like when focused.
        
        NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
        """
        
        tab_nav_response = self.local_ai.ask_llava_about_screenshot(tab_nav_prompt)
        
        try:
            # Extract JSON array
            array_start = tab_nav_response.find("[")
            array_end = tab_nav_response.rfind("]") + 1
            if array_start >= 0 and array_end > array_start:
                actions = json.loads(tab_nav_response[array_start:array_end])
            else:
                self.speak("I couldn't parse the tab navigation actions properly.")
                logging.error(f"Failed to parse tab navigation response: {tab_nav_response}")
                return
                
            # Execute each action
            for action in actions:
                action_type = action.get("type", "")
                
                if action_type == "open_app":
                    self.open_app(action.get("app", ""))
                elif action_type == "focus_element":
                    element = action.get("element", "")
                    if not self.keyboard_tab_navigation(element):
                        # If tab navigation fails, try a different approach
                        self.speak("I had difficulty finding the element with tab navigation. Let me try a different approach.")
                        return self.execute_combined_approach(user_command)
                elif action_type == "type":
                    self.execute_keyboard_action(action.get("text", ""))
                elif action_type == "shortcut":
                    self.execute_keyboard_shortcut(action.get("keys", ""))
                elif action_type == "wait":
                    wait_time = action.get("seconds", 1)
                    logging.info(f"Waiting for {wait_time} seconds...")
                    time.sleep(wait_time)
                    
                # Brief pause between actions
                time.sleep(0.5)
                
                # Verify completion after critical actions
                if action_type in ["open_app", "focus_element", "shortcut"]:
                    if not self.verify_step_completion(f"Verify if action '{action_type}' completed successfully"):
                        self.speak("I encountered an issue with the action. Let me try a different approach.")
                        return self.execute_combined_approach(user_command)
            
            self.speak("Task complete.")
                
        except json.JSONDecodeError as e:
            self.speak("I couldn't parse the tab navigation actions properly.")
            logging.error(f"JSON parsing error: {e}")
            logging.error(f"Tab navigation response: {tab_nav_response}")
        except Exception as e:
            self.speak("I encountered an issue with the tab navigation.")
            logging.error(f"Error: {e}")

    def execute_shortcut_approach(self, user_command):
        logging.info("enter In execute_shortcut_approach function...")
        """Execute using keyboard shortcuts"""
        shortcut_prompt = f"""
        I need to execute this task on a {self.system_info["platform"]} computer: "{user_command}"
        
        Please provide the keyboard shortcuts or simple key sequences needed to accomplish this task.
        Prioritize system-wide shortcuts, Windows key combinations, and efficient command sequences.
        
        Format your response ONLY as a JSON array of objects:
        [
            {{"type": "shortcut", "keys": "win+r"}},
            {{"type": "type", "text": "notepad"}},
            {{"type": "shortcut", "keys": "enter"}},
            {{"type": "wait", "seconds": 2}}
        ]
        
        NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
        """
        
        shortcut_response = self.query_gemini(shortcut_prompt)
        
        try:
            # Extract JSON array
            array_start = shortcut_response.find("[")
            array_end = shortcut_response.rfind("]") + 1
            if array_start >= 0 and array_end > array_start:
                actions = json.loads(shortcut_response[array_start:array_end])
            else:
                self.speak("I couldn't parse the shortcut actions properly.")
                logging.error(f"Failed to parse shortcut response: {shortcut_response}")
                return
                
            # Execute each action
            for action in actions:
                action_type = action.get("type", "")
                
                if action_type == "shortcut":
                    self.execute_keyboard_shortcut(action.get("keys", ""))
                elif action_type == "type":
                    self.execute_keyboard_action(action.get("text", ""))
                elif action_type == "wait":
                    wait_time = action.get("seconds", 1)
                    logging.info(f"Waiting for {wait_time} seconds...")
                    time.sleep(wait_time)
                    
                # Brief pause between actions
                time.sleep(0.5)
                
                # Verify completion after every few actions
                if actions.index(action) % 3 == 0 and actions.index(action) > 0:
                    if not self.verify_step_completion("Verify if actions completed successfully"):
                        self.speak("I encountered an issue. Let me try a different approach.")
                        return self.execute_combined_approach(user_command)
                
            self.speak("Task complete.")
                
        except json.JSONDecodeError as e:
            self.speak("I couldn't parse the shortcut actions properly.")
            logging.error(f"JSON parsing error: {e}")
            logging.error(f"Shortcut response: {shortcut_response}")
        except Exception as e:
            self.speak("I encountered an issue executing the keyboard actions.")
            logging.error(f"Error: {e}")

    def execute_combined_approach(self, user_command):
        logging.info("enter In execute_combined_approach function...")
        """Execute using a combination of methods with visual feedback"""
        # Take initial screenshot
        # screenshot = self.capture_screenshot()
        
        logging.info("Analyzing for combined approach...")
        
        # Send screenshot to Gemini for comprehensive plan
        # combined_prompt = f"""
        # I need to execute this task on a {self.system_info["platform"]} computer: "{user_command}"
        
        # I'm sending you a screenshot of my current screen. Based on this image, provide a comprehensive plan that prioritizes:
        # 1. Command Prompt or PowerShell commands when possible
        # 2. Keyboard shortcuts (especially Win key combinations)
        # 3. Keyboard tab navigation instead of mouse clicks
        
        # My screen resolution is {self.screen_width}x{self.screen_height}.
        
        # Format your response ONLY as a JSON array of action objects:
        # [
        #     {{"type": "open_app", "app": "cmd"}},
        #     {{"type": "wait", "seconds": 2}},
        #     {{"type": "command", "text": "ipconfig"}},
        #     {{"type": "shortcut", "keys": "alt+f4"}},
        # ]
        
        # NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
        # """
            # {{"type": "focus_element", "element": "Search bar", "description": "The main search input at top"}}


        combined_prompt = f"""
            You are an expert virtual assistant for a {self.system_info["platform"]} system. Your job is to create a structured JSON action plan to complete the following user task:

            \"\"\"{user_command}\"\"\"

            You will also receive a screenshot of the current screen to understand the user's environment.

            ## PRIORITIES
            - Use **Command Prompt** or **PowerShell** when possible.
            - Prefer **keyboard shortcuts** (especially Windows key combinations).
            - Use **keyboard navigation** (Tab/Enter) instead of mouse clicks.
            - Avoid mouse clicks entirely unless absolutely necessary.
            - Do **not** add any explanation — only return valid JSON.

            ## SCREEN INFORMATION
            - Screen resolution: {self.screen_width}x{self.screen_height}

            ## FORMAT
            Respond **strictly** as a JSON array of action objects in the format:
            ```json
            [
                {{"type": "open_app", "app": "cmd"}},
                {{"type": "wait", "seconds": 2}},
                {{"type": "command", "text": "ipconfig"}},
                {{"type": "shortcut", "keys": "alt+f4"}}
            ]
            ````

            ## EXAMPLES

            ### 📄 Example 1 – Open Notepad, write content, save

            ```json
            [
                {{"type": "open_app", "app": "notepad"}},
                {{"type": "wait", "seconds": 2}},
                {{"type": "type", "text": "This is a test note."}},
                {{"type": "shortcut", "keys": "ctrl+s"}},
                {{"type": "wait", "seconds": 1}},
                {{"type": "type", "text": "note.txt"}},
                {{"type": "shortcut", "keys": "enter"}}
            ]
            ```

            ### 😂 Example 2 – Tell me a joke using curl

            ```json
            [
                {{"type": "open_app", "app": "cmd"}},
                {{"type": "wait", "seconds": 2}},
                {{"type": "type", "text": "curl https://icanhazdadjoke.com"}},
                {{"type": "shortcut", "keys": "enter"}}
            ]
            ```

            ### 🌐 Example 3 – Open browser and search "Python tutorial"

            ```json
            [
                {{"type": "shortcut", "keys": "win+r"}},
                {{"type": "wait", "seconds": 1}},
                {{"type": "type", "text": "chrome"}},
                {{"type": "shortcut", "keys": "enter"}},
                {{"type": "wait", "seconds": 2}},
                {{"type": "type", "text": "https://www.google.com/search?q=Python+tutorial"}},
                {{"type": "shortcut", "keys": "enter"}}
            ]
            ```

            ### 🔒 Example 4 – Lock the computer

            ```json
            [
                {{"type": "shortcut", "keys": "win+L"}}
            ]
            ```

            ### 🛠️ Example 5 – Open Task Manager

            ```json
            [
                {{"type": "shortcut", "keys": "ctrl+shift+esc"}}
            ]
            ```

            ### 📁 Example 6 – Open File Explorer and go to C:\\

            ```json
            [
                {{"type": "shortcut", "keys": "win+e"}},
                {{"type": "wait", "seconds": 1}},
                {{"type": "type", "text": "C:\\"}},
                {{"type": "shortcut", "keys": "enter"}}
            ]
            ```

            ### 🧹 Example 7 – Clear DNS cache

            ```json
            [
                {{"type": "open_app", "app": "cmd"}},
                {{"type": "wait", "seconds": 2}},
                {{"type": "type", "text": "ipconfig /flushdns"}},
                {{"type": "shortcut", "keys": "enter"}}
            ]
            ```

            ### 📦 Example 8 – Install a package using PowerShell

            ```json
            [
                {{"type": "open_app", "app": "powershell"}},
                {{"type": "wait", "seconds": 2}},
                {{"type": "type", "text": "winget install notepad++"}},
                {{"type": "shortcut", "keys": "enter"}}
            ]
            ```

            ### 💾 Example 9 – Save a webpage as PDF (Print to PDF)

            ```json
            [
                {{"type": "shortcut", "keys": "ctrl+p"}},
                {{"type": "wait", "seconds": 1}},
                {{"type": "type", "text": "Microsoft Print to PDF"}},
                {{"type": "shortcut", "keys": "enter"}},
                {{"type": "wait", "seconds": 1}},
                {{"type": "type", "text": "page.pdf"}},
                {{"type": "shortcut", "keys": "enter"}}
            ]
            ```

            ### 🔍 Example 10 – Open Windows Search and search for 'Device Manager'

            ```json
            [
                {{"type": "shortcut", "keys": "win+s"}},
                {{"type": "wait", "seconds": 1}},
                {{"type": "type", "text": "Device Manager"}},
                {{"type": "shortcut", "keys": "enter"}}
            ]
            ```

            ## REMEMBER:

            * **ONLY output the JSON array**, no text, title, or formatting.
            * **NO explanations**, comments, or trailing output.
            * The actions must be **logical, accurate**, and should work **without mouse usage**.
            * Base your actions on the **screen image and the command** provided.

            Begin.
            """

    

        
        combined_response = self.local_ai.ask_llava_about_screenshot(combined_prompt)
        logging.info(f"Combined response from llava: {combined_response}")
        
        try:
            # Extract JSON array
            array_start = combined_response.find("[")
            array_end = combined_response.rfind("]") + 1
            if array_start >= 0 and array_end > array_start:
                actions = json.loads(combined_response[array_start:array_end])
            else:
                self.speak("I couldn't parse the actions properly.")
                # logging.error(f"Failed to parse combined response: {combined_response}")
                self.ask_perplexity(user_command)
                return
                
            # Execute each action
            steps_completed = 0
            for action in actions:
                action_type = action.get("type", "")
                
                if action_type == "click":
                    # Discourage direct clicking - use tab navigation instead
                    self.speak("Attempting to focus element with keyboard")
                    element_description = f"element at position {action.get('x')}, {action.get('y')}"
                    self.keyboard_tab_navigation(element_description)
                elif action_type == "focus_element":
                    element = action.get("element", "")
                    self.keyboard_tab_navigation(element)
                elif action_type == "type":
                    self.execute_keyboard_action(action.get("text", ""))
                elif action_type == "shortcut":
                    self.execute_keyboard_shortcut(action.get("keys", ""))
                elif action_type == "command":
                    self.execute_cmd_command(action.get("text", ""))
                elif action_type == "open_app":
                    self.open_app(action.get("app", ""))
                elif action_type == "wait":
                    wait_time = action.get("seconds", 1)
                    logging.info(f"Waiting for {wait_time} seconds...")
                    time.sleep(wait_time)
                    
                # Brief pause between actions
                time.sleep(0.5)
                steps_completed += 1
                
                # If we've executed more than 3 actions, take a new screenshot
                # and reassess the remaining actions
                if steps_completed == 3 and len(actions) > 4:
                    logging.info("Reassessing current screen state...")
                    return self.continue_execution(user_command, actions[steps_completed:])
                
            self.speak("Task complete.")
                
        except json.JSONDecodeError as e:
            self.speak("I couldn't parse the actions properly.")
            logging.error(f"JSON parsing error: {e}")
            logging.error(f"Combined response: {combined_response}")
        except Exception as e:
            self.speak("I encountered an issue during execution.")
            logging.error(f"Error: {e}")

    def continue_execution(self, user_command, remaining_actions):
        logging.info("enter In continue_execution function...")
        """Continue execution with visual feedback after screen changes"""
        # Take a new screenshot after the screen has changed
        time.sleep(1)  # Wait for screen to update
        screenshot = self.capture_screenshot()
        
        logging.info("Analyzing current screen state for continued execution...")
        
        # Send screenshot to Gemini for updated plan
        continue_prompt = f"""
        I'm in the middle of executing this task: "{user_command}"
        
        I'm sending you a screenshot of my current screen state. Here are the remaining actions I was planning to execute:
        {json.dumps(remaining_actions, indent=2)}
        
        Based on the current screen state, provide updated actions to complete the task.
        Remember to prioritize Command Prompt, keyboard shortcuts, and tab navigation over mouse clicks.
        
        Format your response ONLY as a JSON array of action objects as before.
        Please also include a "status" field for each action, indicating whether it should still be done or can be skipped:
        [
            {{"type": "type", "text": "example", "status": "do"}},
            {{"type": "shortcut", "keys": "enter", "status": "do"}}
        ]
        
        NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
        """
        
        continue_response = self.local_ai.ask_llava_about_screenshot(continue_prompt)
        
        try:
            # Extract JSON array
            array_start = continue_response.find("[")
            array_end = continue_response.rfind("]") + 1
            if array_start >= 0 and array_end > array_start:
                updated_actions = json.loads(continue_response[array_start:array_end])
            else:
                logging.error(f"Failed to parse continue response: {continue_response}")
                # Fall back to remaining actions
                updated_actions = remaining_actions
                
            # Filter actions based on status
            filtered_actions = []
            for action in updated_actions:
                status = action.get("status", "do")
                if status == "do":
                    # Remove status field before executing
                    if "status" in action:
                        del action["status"]
                    filtered_actions.append(action)
            
            # Execute updated actions
            for action in filtered_actions:
                action_type = action.get("type", "")
                
                if action_type == "click":
                    # Discourage direct clicking - use tab navigation instead
                    self.speak("Attempting to focus element with keyboard")
                    element_description = f"element at position {action.get('x')}, {action.get('y')}"
                    self.keyboard_tab_navigation(element_description)
                elif action_type == "focus_element":
                    element = action.get("element", "")
                    self.keyboard_tab_navigation(element)
                elif action_type == "type":
                    self.execute_keyboard_action(action.get("text", ""))
                elif action_type == "shortcut":
                    self.execute_keyboard_shortcut(action.get("keys", ""))
                elif action_type == "command":
                    self.execute_cmd_command(action.get("text", ""))
                elif action_type == "open_app":
                    self.open_app(action.get("app", ""))
                elif action_type == "wait":
                    wait_time = action.get("seconds", 1)
                    logging.info(f"Waiting for {wait_time} seconds...")
                    time.sleep(wait_time)
                    
                # Brief pause between actions
                time.sleep(0.5)
                
                # Verify completion after critical actions
                if action_type in ["open_app", "focus_element", "command"]:
                    self.verify_step_completion(f"Verify if action '{action_type}' completed successfully")
                
            self.speak("Task complete.")
            return True
                
        except json.JSONDecodeError as e:
            self.speak("I couldn't parse the updated actions properly.")
            logging.error(f"JSON parsing error: {e}")
            logging.error(f"Continue response: {continue_response}")
            return False
        except Exception as e:
            self.speak("I encountered an issue during continued execution.")
            logging.error(f"Error: {e}")
            return False

    def detect_ui_elements(self, screenshot=None):
        """Detect UI elements in the current screen"""
        logging.info("enter In detect_ui_elements function...")
        if screenshot is None:
            screenshot = self.capture_screenshot()
        
        detection_prompt = f"""
        Analyze this screenshot and identify all interactive UI elements.
        For each element, provide its description and what type of element it is (button, input field, link, etc.).
        
        Format your response ONLY as a JSON array:
        [
            {{"description": "Search field", "type": "input", "tab_index": 1}},
            {{"description": "Settings button", "type": "button", "tab_index": 2}},
            ...
        ]
        
        The tab_index should indicate the approximate tab order.
        
        NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
        """
        
        detection_response = self.local_ai.ask_llava_about_screenshot(detection_prompt)
        
        try:
            # Extract JSON array
            array_start = detection_response.find("[")
            array_end = detection_response.rfind("]") + 1
            if array_start >= 0 and array_end > array_start:
                ui_elements = json.loads(detection_response[array_start:array_end])
                return ui_elements
            else:
                logging.error(f"Failed to parse UI element detection response: {detection_response}")
                return []
                
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error for UI detection: {e}")
            return []


    def execute_actions_with_verification(self, actions, user_command, step_description):
        """Execute a list of actions with verification after each action"""
        logging.info("enter In execute_actions_with_verification function...")
        action_count = len(actions)
        
        for i, action in enumerate(actions):
            action_type = action.get("type", "")
            predefined_action = action.get("predefined_action", "none")
            
            # Check if this is a predefined action
            if predefined_action != "none":
                action_success = False
                # Execute the action

                if predefined_action == "open_browser":
                    url = action.get("url", None)
                    action_success = self.predefined_open_browser(url)
                elif predefined_action == "youtube_search":
                    query = action.get("query", "")
                    action_success = self.search_youtube(query)
                elif predefined_action == "google_search":
                    query = action.get("query", "")
                    action_success = self.predefined_google_search(query)
                if action_success:
                    continue  # Skip to next action
    
                # Continue with regular action execution if not predefined

            if action_type == "click":
                x, y = action.get("x"), action.get("y")
                target = action.get("target", "target")
                # action_success = self.execute_mouse_action(x, y, "click", target)
            # elif action_type == "doubleclick":
            #     x, y = action.get("x"), action.get("y")
            #     target = action.get("target", "target")
            #     action_success = self.execute_mouse_action(x, y, "doubleclick", target)
            # elif action_type == "rightclick":
            #     x, y = action.get("x"), action.get("y")
            #     target = action.get("target", "target")
            #     action_success = self.execute_mouse_action(x, y, "rightclick", target)
            elif action_type == "type":
                self.execute_keyboard_action(action.get("text", ""))
                action_success = True
            elif action_type == "shortcut":
                self.execute_keyboard_shortcut(action.get("keys", ""))
                action_success = True
            elif action_type == "command":
                self.execute_cmd_command(action.get("text", ""))
                action_success = True
            elif action_type == "open_app":
                self.open_app(action.get("app", ""))
                action_success = True
            elif action_type == "wait":
                wait_time = action.get("seconds", 1)
                logging.info(f"Waiting for {wait_time} seconds...")
                time.sleep(wait_time)
                action_success = True
                
            # Brief pause between actions
            time.sleep(0.5)
            
            # Verify action success if not the last action
            if i < action_count - 1 and action_type != "wait":
                # Take screenshot for verification
                # screenshot_base64, _ = self.capture_screenshot()
                
                # Verify if the action was successful
                verify_prompt = f"""
                I just performed this action: {json.dumps(action)}
                
                This was part of step: "{step_description}" for the task: "{user_command}"
                
                Based on the screenshot, was this action successful? 
                
                Format your response ONLY as a JSON object:
                {{
                    "success": true/false,
                    "reasoning": "Brief explanation",
                    "next_action": "proceed" or "retry" or "fallback"
                }}
                
                NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
                """
                
                verify_response = self.local_ai.ask_llava_about_screenshot(verify_prompt)
                # verify_response = self.query_gemini_with_image(verify_prompt, screenshot_base64)
                
                try:
                    # Extract JSON
                    json_start = verify_response.find("{")
                    json_end = verify_response.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        verification = json.loads(verify_response[json_start:json_end])
                    else:
                        # Default to proceed
                        verification = {"success": True, "next_action": "proceed"}
                        
                    success = verification.get("success", False)
                    next_action = verification.get("next_action", "proceed")
                    
                    logging.info(f"Action verification - Success: {success}, Next: {next_action}")

                    if not success:
                        if next_action == "retry":
                            # Try one more time
                            logging.info("Retrying the action...")
                            # self.speak("Retrying the previous action.")
                            
                            # # Re-execute the same action
                            # if action_type == "click":
                            #     x, y = action.get("x"), action.get("y")
                            #     target = action.get("target", "target")
                            #     # self.execute_mouse_action(x, y, "click", target)
                            # # elif action_type == "doubleclick":
                            # #     x, y = action.get("x"), action.get("y")
                            # #     target = action.get("target", "target")
                            # #     self.execute_mouse_action(x, y, "doubleclick", target)
                            # # elif action_type == "rightclick":
                            # #     x, y = action.get("x"), action.get("y")
                            # #     target = action.get("target", "target")
                            # #     self.execute_mouse_action(x, y, "rightclick", target)
                            # elif action_type == "type":
                            #     self.execute_keyboard_action(action.get("text", ""))
                            # elif action_type == "shortcut":
                            #     self.execute_keyboard_shortcut(action.get("keys", ""))
                            # elif action_type == "command":
                            #     self.execute_cmd_command(action.get("text", ""))
                            # elif action_type == "open_app":
                            #     self.open_app(action.get("app", ""))
                                
                        elif next_action == "fallback":
                            # Use fallback for the remaining step
                            logging.info("Using fallback method...")
                            self.speak("Using alternative approach for this step.")
                            # self.fallback_execution(user_command, step_description)
                            return
                    
                except json.JSONDecodeError as e:
                    logging.error(f"JSON parsing error in verification: {e}")
                    # Continue with next action
                
        # After all actions are executed
        # Final verification for the entire step
        screenshot_base64, _ = self.capture_screenshot()
        
        final_verify_prompt = f"""
        I've completed all actions for this step: "{step_description}" 
        Part of the task: "{user_command}"
        
        Based on the screenshot, was this step completed successfully?
        
        Format your response ONLY as a JSON object:
        {{
            "success": true/false,
            "reasoning": "Brief explanation",
            "next_action": "proceed" or "fallback"
        }}
        
        NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
        """
        
        final_verify_response = self.local_ai.ask_llava_about_screenshot(final_verify_prompt)
        
        try:
            # Extract JSON
            json_start = final_verify_response.find("{")
            json_end = final_verify_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                final_verification = json.loads(final_verify_response[json_start:json_end])
            else:
                # Default to proceed
                final_verification = {"success": True, "next_action": "proceed"}
                
            success = final_verification.get("success", False)
            next_action = final_verification.get("next_action", "proceed")
            
            logging.info(f"Step verification - Success: {success}, Next: {next_action}")
            
            if not success and next_action == "fallback":
                # Use fallback for this step
                logging.info("Using fallback method for step completion...")
                self.speak("The step wasn't completed successfully. Using alternative approach.")
                self.fallback_execution(user_command, step_description)
            else:
                self.speak(f"Step completed: {step_description}")
                
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error in final verification: {e}")
            # Continue with next step

    def fallback_execution(self, user_command, current_step):
        """Fallback mechanism if step execution fails"""
        logging.info("enter In fallback_execution function...")
        # Take screenshot
        screenshot_base64, _ = self.capture_screenshot()
        
        logging.info("Using fallback execution...")
        
        # Ask Gemini what to do next based on current screen
        fallback_prompt = f"""
        I was trying to execute this task: "{user_command}"
        
        Specifically, I was working on this step: "{current_step}"
        
        But I encountered difficulties. Based on the current screen state, what should I do next to continue?
        
        Format your response ONLY as a JSON array of action objects:
        [
            {{"type": "type", "text": "notepad"}},
            {{"type": "shortcut", "keys": "win+r"}},
            {{"type": "wait", "seconds": 2}}
        ]
        
        For click actions, ALWAYS include a "target" field with a description of what's being clicked.
        NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
        """
            # {{"type": "click", "x": 100, "y": 200, "target": "Start button"}},
        
        fallback_response = self.local_ai.ask_llava_about_screenshot(fallback_prompt)
        
        try:
            # Extract JSON array
            array_start = fallback_response.find("[")
            array_end = fallback_response.rfind("]") + 1
            if array_start >= 0 and array_end > array_start:
                fallback_actions = json.loads(fallback_response[array_start:array_end])
            else:
                self.speak("I couldn't determine how to proceed.")
                logging.error(f"Failed to parse fallback response: {fallback_response}")
                return
                
            # Execute fallback actions
            self.speak("Trying an alternative approach.")
            self.execute_actions_with_verification(fallback_actions, user_command, current_step)
                
        except json.JSONDecodeError as e:
            self.speak("I couldn't determine how to proceed.")
            logging.error(f"JSON parsing error: {e}")
            logging.error(f"Fallback response: {fallback_response}")
        except Exception as e:
            self.speak("I encountered an issue with the fallback approach.")

    # def execute_combined_approach(self, user_command):
    #     """Execute using a combination of methods with visual feedback - fallback method"""
    #     logging.info("enter In execute_combined_approach function...")
    #     # Take initial screenshot
    #     # screenshot_base64, _ = self.capture_screenshot()
        
    #     logging.info("Using combined approach as fallback...")
    #     self.speak("Using comprehensive approach for this task.")
        
    #     # Send screenshot to Gemini for comprehensive plan
    #     combined_prompt = f"""
    #     I need to execute this task on a {self.system_info["platform"]} computer: "{user_command}"
        
    #     Based on this screenshot of my current screen, provide a comprehensive plan using a combination of GUI actions, keyboard actions, and Command Prompt commands as needed.
        
    #     My screen resolution is {self.screen_width}x{self.screen_height}.
        
    #     Format your response ONLY as a JSON array of action objects:
    #     [
    #         {{"type": "shortcut", "target": "Start menu", "keys": "win"}},
    #         {{"type": "type", "text": "notepad"}},
    #         {{"type": "shortcut", "keys": "win+r"}},
    #         {{"type": "wait", "seconds": 2}}
    #     ]
        
    #     For click actions, ALWAYS include a "target" field with a description of what's being clicked.
    #     NO OTHER OUTPUT OR EXPLANATION IS NEEDED.
    #     """
    #     combined_response = self.query_gemini(combined_prompt)
    #     # combined_response = self.query_gemini_with_image(combined_prompt, screenshot_base64)
        
    #     try:
    #         # Extract JSON array
    #         array_start = combined_response.find("[")
    #         array_end = combined_response.rfind("]") + 1
    #         if array_start >= 0 and array_end > array_start:
    #             actions = json.loads(combined_response[array_start:array_end])
    #         else:
    #             self.speak("I couldn't plan the task properly.")
    #             logging.error(f"Failed to parse combined response: {combined_response}")
    #             return
                
    #         # Execute actions with verification
    #         self.execute_actions_with_verification(actions, user_command, "Comprehensive approach")
                
    #     except json.JSONDecodeError as e:
    #         self.speak("I couldn't parse the plan for this task.")
    #         logging.error(f"JSON parsing error: {e}")
    #         logging.error(f"Combined response: {combined_response}")
    #     except Exception as e:
    #         self.speak("I encountered an issue with this task.")
    #         logging.error(f"Error: {e}")

    def smart_recovery(self, user_command):
        logging.info("enter In smart_recovery function...")
        """Smart recovery when the execution path is unclear"""
        # Take a screenshot for analysis
        screenshot_base64, _ = self.capture_screenshot()
        
        logging.info("Using smart recovery to determine current state...")
        self.speak("Analyzing the current screen to determine how to proceed.")
        
        # Ask Gemini for analysis and recovery plan
        recovery_prompt = f"""
        I was trying to execute this task: "{user_command}"
        
        But I seem to be stuck or unsure how to proceed. Based on the current screen state:
        1. What is the current state of the task?
        2. What should I do next to complete the task?
        
        Format your response as a JSON object:
        {{
            "current_state": "Description of what's currently visible/happening",
            "progress_percentage": 50,  # Estimated percentage of task completion
            "next_actions": [
                {{"type": "click", "x": 100, "y": 200, "target": "Button description"}},
                {{"type": "type", "text": "text to type"}},
                # more actions as needed
            ]
        }}
        
        For click actions, ALWAYS include a "target" field with a description of what's being clicked.
        """
        
        recovery_response = self.local_ai.ask_llava_about_screenshot(recovery_prompt)
        
        try:
            # Extract JSON
            json_start = recovery_response.find("{")
            json_end = recovery_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                recovery_plan = json.loads(recovery_response[json_start:json_end])
            else:
                self.speak("I couldn't analyze the current state properly.")
                logging.error(f"Failed to parse recovery response: {recovery_response}")
                return
                
            current_state = recovery_plan.get("current_state", "Unknown state")
            progress = recovery_plan.get("progress_percentage", 0)
            next_actions = recovery_plan.get("next_actions", [])
            
            self.speak(f"Current state: {current_state}. Task is approximately {progress}% complete.")
            
            if next_actions:
                self.speak("Continuing with the execution.")
                self.execute_actions_with_verification(next_actions, user_command, "Recovery")
            else:
                self.speak("I'm unable to determine how to proceed.")
                
        except json.JSONDecodeError as e:
            self.speak("I couldn't analyze the current state properly.")
            logging.error(f"JSON parsing error: {e}")
        except Exception as e:
            self.speak("I encountered an issue with recovery.")
            logging.error(f"Error: {e}")

    def check_correct_application(self, expected_app):
        logging.info("enter In check_correct_application function...")
        """Check if the correct application is in focus"""
        screenshot_base64, _ = self.capture_screenshot()
        
        app_check_prompt = f"""
        Based on this screenshot, is {expected_app} currently open and in focus?
        
        Format your response as a JSON object:
        {{
            "is_correct_app": true/false,
            "app_name": "Actual application that appears to be in focus",
            "confidence": 90  # 0-100 confidence level in this assessment
        }}
        """
        
        # app_check_response = self.local_ai.ask_llava_about_screenshot(app_check_prompt, screenshot_base64)
        
        # try:
        #     # Extract JSON
        #     json_start = app_check_response.find("{")
        #     json_end = app_check_response.rfind("}") + 1
        #     if json_start >= 0 and json_end > json_start:
        #         app_check = json.loads(app_check_response[json_start:json_end])
        #     else:
        #         # Default to assuming the app is correct
        #         return True
                
        #     is_correct = app_check.get("is_correct_app", False)
        #     actual_app = app_check.get("app_name", "unknown")
        #     confidence = app_check.get("confidence", 0)
            
        #     logging.info(f"App check - Correct: {is_correct}, Actual: {actual_app}, Confidence: {confidence}%")
            
        #     return is_correct
            
        # except json.JSONDecodeError as e:
        #     logging.error(f"JSON parsing error in app check: {e}")
        #     # Default to assuming the app is correct
        #     return True
        # except Exception as e:
        #     logging.error(f"Error checking application: {e}")
        #     # Default to assuming the app is correct
        #     return True

    def execute_multimedia_task(self, user_command):
        logging.info("enter In execute_multimedia_task function...")
        """Execute tasks specific to multimedia applications (YouTube, video players, etc.)"""
        # First determine if this is a multimedia-related task
        analysis_prompt = f"""
        Analyze this task: "{user_command}"
        
        Does this task involve working with multimedia applications like:
        - YouTube
        - Video players
        - Music players
        - Streaming services
        
        Format your response as a JSON object:
        {{
            "is_multimedia": true/false,
            "app_name": "Name of the multimedia app involved (if any)",
            "action_type": "play" or "pause" or "volume" or "seek" or "other"
        }}
        """
        
        analysis_response = self.query_gemini(analysis_prompt)
        
        # try:
        #     # Extract JSON
        #     json_start = analysis_response.find("{")
        #     json_end = analysis_response.rfind("}") + 1
        #     if json_start >= 0 and json_end > json_start:
        #         analysis = json.loads(analysis_response[json_start:json_end])
        #     else:
        #         # Proceed with regular task execution
        #         return self.execute_step_by_step_task(user_command)
                
        #     is_multimedia = analysis.get("is_multimedia", False)
        #     app_name = analysis.get("app_name", "")
        #     action_type = analysis.get("action_type", "other")
            
        #     if not is_multimedia:
        #         # Proceed with regular task execution
        #         return self.execute_step_by_step_task(user_command)
                
        #     # Check if we need to open the multimedia app first
        #     if app_name:
        #         # Check if the app is already open
        #         app_is_open = self.check_correct_application(app_name)
                
        #         if not app_is_open:
        #             self.speak(f"Opening {app_name} first.")
        #             self.open_app(app_name)
        #             time.sleep(3)  # Wait for app to open
            
        #     # Now handle the specific action based on the multimedia content
        #     screenshot_base64, _ = self.capture_screenshot()
            
            # media_prompt = f"""
            # I need to execute this multimedia-related task: "{user_command}"                                                            
            
            # Based on the screenshot, provide precise steps to interact with the media player or website.
            
            # My screen resolution is {self.screen_width}x{self.screen_height}.
            
            # Format your response ONLY as a JSON array of action objects:
            # [
            #     {{"type": "shortcut", "keys": "space"}},
            #     {{"type": "wait", "seconds": 2}}
            # ]
            
            # For click actions, ALWAYS include a "target" field with a description of what's being clicked.
            # Pay special attention to locating the correct controls for {action_type}.
            # """
                # {{"type": "click", "x": 100, "y": 200, "target": "Play button"}},
            
        #     media_response = self.local_ai.ask_llava_about_screenshot(media_prompt, screenshot_base64)
        #     # media_response = self.query_gemini_with_image(media_prompt, screenshot_base64)
            
        #     # Extract and execute the actions
        #     try:
        #         # Extract JSON array
        #         array_start = media_response.find("[")
        #         array_end = media_response.rfind("]") + 1
        #         if array_start >= 0 and array_end > array_start:
        #             media_actions = json.loads(media_response[array_start:array_end])
        #         else:
        #             self.speak("I couldn't determine how to interact with the media.")
        #             logging.error(f"Failed to parse media response: {media_response}")
        #             return self.execute_step_by_step_task(user_command)
                    
        #         # Execute with extra precision for media controls
        #         self.speak(f"Executing media controls for {app_name if app_name else 'the application'}.")
        #         self.execute_actions_with_verification(media_actions, user_command, f"Media control: {action_type}")
                    
        #     except json.JSONDecodeError as e:
        #         self.speak("I couldn't determine how to interact with the media.")
        #         logging.error(f"JSON parsing error: {e}")
        #         return self.execute_step_by_step_task(user_command)
                
        # except json.JSONDecodeError as e:
        #     logging.error(f"JSON parsing error in multimedia analysis: {e}")
        #     # Proceed with regular task execution
        #     return self.execute_step_by_step_task(user_command)
        # except Exception as e:
        #     logging.error(f"Error in multimedia task: {e}")
        #     # Proceed with regular task execution
        #     return self.execute_step_by_step_task(user_command)

    def toggle_context(self, enable=None):
        """Toggle context maintenance or set to specific value"""
        if enable is not None:
            self.maintain_context = enable
        else:
            self.maintain_context = not self.maintain_context
            
        status = "enabled" if self.maintain_context else "disabled"
        self.speak(f"Context maintenance is now {status}.")
        if not self.maintain_context:
            self.conversation_history = []
            self.speak("Conversation history has been cleared.")

    def remove_thinking_tags(self, text):
        """
        Remove <think>...</think> tags from DeepSeek R1 model output.
        
        Args:
            text (str): The raw text output from the model
            
        Returns:
            str: Cleaned text without thinking tags
        """
        if not text:
            return text
            
        # Simple regex approach to remove everything between and including <think> tags
        import re
        cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # Alternative approach: find everything between tags if regex fails
        if '<think>' in cleaned_text or '</think>' in cleaned_text:
            try:
                # Manual extraction approach as fallback
                start_idx = text.find('<think>')
                if start_idx != -1:
                    end_idx = text.find('</think>', start_idx)
                    if end_idx != -1:
                        # Remove the tagged section including the tags
                        cleaned_text = text[:start_idx] + text[end_idx + len('</think>'):]
            except Exception as e:
                logging.warning(f"Error in manual thinking tag removal: {str(e)}")
        
        # Clean up any potential double spaces or extra line breaks from removal
        cleaned_text = re.sub(r'\n\s*\n', '\n\n', cleaned_text)
        cleaned_text = re.sub(r' +', ' ', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        return cleaned_text

# def extract_json_block(text):
#     match = re.search(r'\{.*?\}', text, re.DOTALL)
#     return match.group(0) if match else None
def extract_json_block(text):
    # Remove <think>...</think> or any other XML-style tags
    cleaned = re.sub(r"<[^>]+>.*?</[^>]+>", "", text, flags=re.DOTALL)
    brace_count = 0
    start = None

    for i, char in enumerate(cleaned):
        if char == '{':
            if brace_count == 0:
                start = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start is not None:
                return cleaned[start:i + 1]

    return None  # if no valid JSON block is found
def extract_json_array(text):
    brace_count = 0
    start = None

    for i, char in enumerate(text):
        if char == '[':
            if brace_count == 0:
                start = i   
            brace_count += 1
        elif char == ']':
            brace_count -= 1
            if brace_count == 0:
                return text[start:i + 1]
    return None  # if no valid JSON array is found  
def extract_json_object(text):
    brace_count = 0
    start = None

    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start is not None:
                return text[start:i + 1]
    return None  # if no valid JSON object is found




def main():
    # Get API key from environment variable or user input
    gemini_api_key = "AIzaSyCACmA9NwFINrLSw7F6mo1P8PJzVdswIPA"
    # gemini_api_key = "AIzaSyCtcXpKqIpyp2rd2Felgq2d8GEK90oVLQI"
    if not gemini_api_key:
        gemini_api_key = input("Please enter your Gemini API key: ")
    
    # Allow context to be enabled/disabled
    context_enabled = False
    # context_input = input("Enable context between commands? (y/n, default: y): ")
    # if context_input.lower() == 'n':
        # context_enabled = False
    # global listener
    listener = JarvisListener()
    # listener.start_continuous_listening()
    jarvis = JarvisAssistant(gemini_api_key, maintain_context=context_enabled)
    
    jarvis.speak("Hi Boss, am Jarvis, how can i help you today")
    # jarvis.speak("Jarvis initialized and ready.")
    
    try:
        # Initial timeout of None means wait indefinitely for the first command
        idle_timeout = 60

        while True:
            # Get command from user
            print(f"\nWaiting for a command{' (20s timeout)' if idle_timeout else ''}...")
            # command = listener.get_next_command(timeout=idle_timeout)
            # command = listener.listen_for_command()


            print("Waiting 10 seconds for next command...")
            command = listener.listen_for_command_with_timeout(60)
            if command and command.lower() in ["exit", "quit", "goodbye", "bye", "shutdown", "stop", "terminate", "shutoff"]:
                jarvis.speak("Shutting down.")
                break
            jarvis.process_command(command)
            # command = input("Enter command (or 'exit' to quit, 'toggle_context' to toggle context): ")
            
            # if command.lower() in ["exit", "quit", "goodbye", "bye", "shutdown", "stop", "terminate", "shutoff"]:
            #     jarvis.speak("Shutting down.")
            #     break


            # if command is None:
            #     # Timeout occurred
            #     print("No command received in 10 seconds. Terminating program.")
            #     break

             # Process the command in a separate thread
            # execution_thread = listener.execute_command(command, jarvis.process_command)
            # execution_thread.join()
            
            # After first command, set timeout to 10 seconds for next command
            # idle_timeout = 10
            # elif command.lower() == "toggle_context":
            #     jarvis.toggle_context()
            #     continue
            
            # if command:
            #     print("Executing command: '{}'".format(command))
            #     # Process the command with new handling methods
            #     jarvis.process_command(command)

            #     print("Waiting 10 seconds for next command...")
            #     command = listener.listen_for_command_with_timeout(10)
            #     # jarvis.process_command(command)
            #     if command is None:
            #         print("No command received in 10 seconds. Terminating program.")
            #         break
            #     else:
            #         print("Executing command: '{}'".format(command))
            #         jarvis.process_command(command)
            # else:
            #     print("No command detected after wake word.")
    except KeyboardInterrupt:
        print("Program terminated by user")
    finally:
        # Clean up resources
        # Clean up
        # listener.stop_continuous_listening()
        if hasattr(jarvis, 'web_manager'):
            jarvis.web_manager.close()
            jarvis.local_ai.stop_model()
        logging.info("Jarvis shutdown complete")















class TaskManager:
    def __init__(self, jarvis_assistant):
        self.jarvis = jarvis_assistant

        self.ui_manager = UIAutomationManager(jarvis_assistant)
        self.web_manager = WebAutomationManager(jarvis_assistant)
        self.logger = logging.getLogger("TaskManager")
        
    def set_alarm(self, time_string):
        logging.info("enter In set_alarm function...")
        """Set alarm using Windows alarm app"""
        try:
            # Open Alarms & Clock app
            self.jarvis.open_app("Alarms & Clock")
            time.sleep(2)
            
            # Find and click the "Add new alarm" button
            add_button = self.ui_manager.find_button_by_text("New alarm")
            if not add_button:
                add_button = self.ui_manager.find_button_by_text("+")
                
            if add_button:
                self.ui_manager.click_element(add_button)
                time.sleep(1)
                
                # Set time using UI automation
                # This will need to be adjusted based on the actual UI
                hour_selector = self.ui_manager.find_element_by_automation_id("HourSelector")
                minute_selector = self.ui_manager.find_element_by_automation_id("MinuteSelector")
                
                # Parse the time string
                parsed_time = time_string.replace(":", " ").split()
                hour = parsed_time[0]
                minute = parsed_time[1]
                
                if hour_selector and minute_selector:
                    # Set hour and minute
                    hour_selector.SendKeys(hour)
                    minute_selector.SendKeys(minute)
                    
                    # Find and click Save button
                    save_button = self.ui_manager.find_button_by_text("Save")
                    if save_button:
                        self.ui_manager.click_element(save_button)
                        self.jarvis.speak(f"Alarm set for {time_string}")
                        return True
                        
            self.jarvis.speak("I couldn't set the alarm using UI automation. Falling back to keyboard method.")
            # Fallback to pyautogui method
            return self.jarvis.execute_step_by_step_task(f"Set alarm for {time_string}")
        except Exception as e:
            self.logger.error(f"Error setting alarm: {e}")
            self.jarvis.speak(f"I encountered an error setting the alarm: {str(e)}")
            return False
            
    def send_whatsapp_message(self, contact_name, message):
        """Send WhatsApp message to a contact"""
        logging.info("enter In send_whatsapp_message function...")
        try:
            # Open WhatsApp Desktop/Web
            # self.jarvis.open_app("WhatsApp")
            self.jarvis.execute_cmd_command("start https://web.whatsapp.com/")
            time.sleep(5)  # Wait for WhatsApp to load
            
            # Find search box
            search_box = self.ui_manager.find_element_by_name("Search")
            if not search_box:
                search_box = self.ui_manager.find_element_by_automation_id("searchTextBox")
                
            if search_box:
                self.ui_manager.click_element(search_box)
                time.sleep(0.5)
                self.ui_manager.type_text(search_box, contact_name)
                time.sleep(2)  # Wait for search results
                
                # Find and click on the contact
                contact = self.ui_manager.find_element_by_name(contact_name)
                if contact:
                    self.ui_manager.click_element(contact)
                    time.sleep(1)
                    
                    # Find message input field
                    message_box = self.ui_manager.find_element_by_name("Type a message")
                    if message_box:
                        self.ui_manager.click_element(message_box)
                        self.ui_manager.type_text(message_box, message)
                        time.sleep(0.5)
                        pyautogui.press('enter')  # Send message
                        self.jarvis.speak(f"Message sent to {contact_name}")
                        return True
                        
            self.jarvis.speak("I couldn't send the WhatsApp message using UI automation. Falling back to standard method.")
            # Fallback to pyautogui method
            return self.jarvis.execute_step_by_step_task(f"Send WhatsApp message to {contact_name} saying {message}")
        except Exception as e:
            self.logger.error(f"Error sending WhatsApp message: {e}")
            self.jarvis.speak(f"I encountered an error sending the message: {str(e)}")
            return False
            
    def read_screen_content(self):
        logging.info("enter In read_screen_content function...")
        """Read what's currently on screen"""
        try:
            screen_text = self.ui_manager.get_window_text()
            if screen_text:
                # Clean up the text
                screen_text = ' '.join(screen_text.split())
                
                # Summarize if too long
                if len(screen_text) > 500:
                    prompt = f"Summarize this text from the screen in 2-3 sentences: {screen_text}"
                    summary = self.jarvis.query_gemini(prompt)
                    self.jarvis.speak(summary)
                else:
                    self.jarvis.speak(f"I can see the following on screen: {screen_text}")
                return True
            else:
                self.jarvis.speak("I couldn't extract readable text from the screen.")
                return False
        except Exception as e:
            self.logger.error(f"Error reading screen content: {e}")
            self.jarvis.speak("I encountered an error trying to read the screen.")
            return False
            
    def search_ai_and_report(self, query, ai_service="perplexity"):
        logging.info("enter In search_ai_and_report function...")
        """Search AI service and report findings"""
        try:
            self.jarvis.speak(f"Searching {ai_service} for information about: {query}")
            
            if ai_service.lower() == "chatgpt":
                results = self.web_manager.search_chatgpt(query)
            elif ai_service.lower() == "perplexity":
                results = self.web_manager.search_perplexity(query)
            else:
                self.jarvis.speak(f"I don't know how to search {ai_service}.")
                return False
                
            if results:
                # Summarize if very long
                results = self.jarvis.remove_thinking_tags(results)
                if len(results) > 600:
                    prompt = f"Summarize this concisely while preserving key information: {results}"
                    summary = self.jarvis.query_gemini(prompt)
                    results = self.jarvis.remove_thinking_tags(summary)
                    self.jarvis.speak(results)
                else:
                    self.jarvis.speak(results)
                return True
            else:
                self.jarvis.speak(f"I couldn't get results from {ai_service}.")
                return False
        except Exception as e:
            self.logger.error(f"Error with AI search: {e}")
            self.jarvis.speak(f"I encountered an error searching {ai_service}: {str(e)}")
            return False
            
    def read_email_from_gmail(self, count=3):
        logging.info("enter In read_email_from_gmail function...")
        """Read recent emails from Gmail"""
        try:
            # Open Gmail
            self.web_manager.driver.get("https://mail.google.com")
            time.sleep(5)  # Wait for load
            
            # Check if login required
            if "Sign in" in self.web_manager.driver.title:
                self.jarvis.speak("Please log in to Gmail. I'll wait.")
                # Wait for login to complete
                WebDriverWait(self.web_manager.driver, 60).until(
                    lambda driver: "inbox" in driver.current_url.lower()
                )
            
            # Wait for inbox to load
            WebDriverWait(self.web_manager.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tr.zA"))
            )
            
            # Get emails
            email_rows = self.web_manager.driver.find_elements(By.CSS_SELECTOR, "tr.zA")[:count]
            emails = []
            
            for row in email_rows:
                try:
                    sender = row.find_element(By.CSS_SELECTOR, ".yP,.zF").get_attribute("email") or row.find_element(By.CSS_SELECTOR, ".yP,.zF").text
                    subject = row.find_element(By.CSS_SELECTOR, ".y6").text
                    snippet = row.find_element(By.CSS_SELECTOR, ".y6+div").text
                    emails.append(f"From {sender}: {subject}. {snippet}")
                except:
                    continue
            
            if emails:
                self.jarvis.speak(f"Here are your {len(emails)} most recent emails:")
                for email in emails:
                    self.jarvis.speak(email)
                return True
            else:
                self.jarvis.speak("I couldn't find any emails to read.")
                return False
        except Exception as e:
            self.logger.error(f"Error reading emails: {e}")
            self.jarvis.speak("I encountered an error trying to read your emails.")
            return False






















import pywinauto
from pywinauto import Application, Desktop
import uiautomation as auto
import pygetwindow as gw
import pytesseract


class UIAutomationManager:
    def __init__(self, jarvis_assistant):
        self.jarvis = jarvis_assistant
        self.desktop = Desktop()
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Update path as needed
        self.logger = logging.getLogger("UIAutomation")
        
    def find_element_by_name(self, name):
        logging.info("enter In find_element_by_name function...")
        """Find UI element by name using UIA"""
        try:
            element = auto.WindowControl(Name=name)
            if element.Exists(3):  # Wait up to 3 seconds
                return element
            return None
        except Exception as e:
            self.logger.error(f"Error finding element by name: {e}")
            return None
            
    def find_element_by_automation_id(self, automation_id):
        logging.info("enter In find_element_by_automation_id function...")
        """Find UI element by automation ID"""
        try:
            element = auto.FindFirstElementByAutomationId(automation_id)
            return element
        except Exception as e:
            self.logger.error(f"Error finding element by automation ID: {e}")
            return None
            
    def find_button_by_text(self, text):
        logging.info("enter In find_button_by_text function...")
        """Find button containing text"""
        try:
            button = auto.ButtonControl(Name=text)
            if button.Exists(3):
                return button
            return None
        except Exception as e:
            self.logger.error(f"Error finding button: {e}")
            return None
            
    def get_active_window(self):
        logging.info("enter In get_active_window function...")
        """Get currently active window"""
        try:
            return gw.getActiveWindow()
        except Exception as e:
            self.logger.error(f"Error getting active window: {e}")
            return None
            
    def connect_to_application(self, process_name=None, window_name=None):
        logging.info("enter In connect_to_application function...")
        """Connect to running application"""
        try:
            if process_name:
                app = Application().connect(process=process_name)
            elif window_name:
                app = Application().connect(title=window_name)
            else:
                return None
            return app
        except Exception as e:
            self.logger.error(f"Error connecting to application: {e}")
            return None
            
    def get_window_text(self):
        logging.info("enter In get_window_text function...")
        """Extract text from active window using OCR"""
        try:
            screenshot = ImageGrab.grab()
            text = pytesseract.image_to_string(screenshot)
            return text
        except Exception as e:
            self.logger.error(f"Error extracting text from window: {e}")
            return ""
            
    def click_element(self, element):
        logging.info("enter In click_element function...")
        """Click on a UI element"""
        try:
            if element:
                element.Click()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error clicking element: {e}")
            return False
            
    def type_text(self, element, text):
        logging.info("enter In type_text function...")
        """Type text into a UI element"""
        try:
            if element:
                element.SetFocus()
                auto.SendKeys(text)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error typing text: {e}")
            return False
        












import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import urllib.parse

class WebAutomationManager:
    def __init__(self, jarvis_assistant, headless=True):
        self.jarvis = jarvis_assistant
        self.logger = logging.getLogger("WebAutomation")
        self.session = requests.Session()
        self.driver = None
        self.headless = headless
        
    def setup_selenium(self):
        """Set up Selenium WebDriver"""
        logging.info("enter In setup_selenium function...")
        if self.driver is not None:
            return  # already initialized
        
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.logger.info("Selenium WebDriver initialized successfully")
            return
        except Exception as e:
            self.logger.error(f"Error setting up Selenium: {e}")

    def close(self):
        logging.info("enter In close function...")
        if self.driver:
            self.driver.quit()
            self.driver = None  # important to set None after closing
            
    def scrape(self, url, wait_time=2):
        try:
            if not self.driver:
                self.setup_selenium()
            
            self.logger.info(f"Opening URL: {url}")
            self.driver.get(url)

            time.sleep(wait_time)  # Wait for JavaScript to load
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # Optional: extract main content heuristically
            main_content = (
                soup.find('main') or
                soup.find('article') or
                soup.find('div', class_='content') or
                soup.find('div', class_='result')
            )

            if main_content:
                logging.info(f"Extracted content:::: {main_content.get_text(separator='\n', strip=True)}")
                return main_content.get_text(separator='\n', strip=True)
            return soup.get_text(separator='\n', strip=True)

        except Exception as e:
            self.logger.exception("Error scraping page")
            return None

    def get_webpage(self, url):
        logging.info("enter In get_webpage function...")
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"Error fetching webpage: {e}")
            return None

    def search_chatgpt(self, query):
        logging.info("Using PyAutoGUI with mouse movements to access ChatGPT...")
        try:
            import pyautogui
            import time
            import os
            import pyperclip
            import random
            
            # Get screen dimensions
            screen_width, screen_height = pyautogui.size()
            center_x, center_y = screen_width // 2, screen_height // 2
            
            # Open a browser window (this assumes you have Chrome installed)
            os.system('start chrome --new-window "https://chatgpt.com"')
            time.sleep(5)  # Wait for browser to open
            
            # Navigate to search
            pyautogui.hotkey('ctrl', 'l')  # Focus address bar
            time.sleep(0.5)
            pyperclip.copy(f"https://chatgpt.com/search?q={urllib.parse.quote(query)}")
            pyautogui.hotkey('ctrl', 'v')  # Paste URL
            time.sleep(0.3)
            pyautogui.press('enter')
            time.sleep(12)  # Wait for page to load
            
            # Add human-like mouse movement - move to center of screen with slight randomization
            target_x = center_x + random.randint(-50, 50)
            target_y = center_y + random.randint(-50, 50)
            
            # Move mouse smoothly to simulate human movement
            pyautogui.moveTo(target_x, target_y, duration=1.5)
            time.sleep(0.5)
            
            # Click to ensure focus is on the content area
            pyautogui.click()
            time.sleep(1)
            
            # Scroll down a bit to see more content
            for _ in range(2):
                pyautogui.scroll(-300)  # Scroll down
                time.sleep(random.uniform(0.5, 1.2))
            
            # Take a screenshot to verify what we're seeing
            # screenshot = pyautogui.screenshot()
            # screenshot_path = f"pyautogui_screenshot_{int(time.time())}.png"
            # screenshot.save(screenshot_path)
            # logging.info(f"Screenshot saved to {screenshot_path}")
            
            # Move to an area likely to contain text (slightly below center)
            text_area_x = center_x + random.randint(-100, 100)
            text_area_y = center_y + random.randint(50, 150)  # Below center where content likely is
            
            pyautogui.moveTo(text_area_x, text_area_y, duration=1.0)
            time.sleep(0.3)
            
            # Triple-click to select a paragraph of text
            pyautogui.tripleClick()
            time.sleep(0.3)
            
            # Copy the selected text
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.5)
            paragraph = pyperclip.paste()
            

            
            # Combine unique paragraphs (avoid duplicates)
            # paragraphs = [paragraph.strip() for paragraph in paragraph.split('\n') if paragraph.strip()]
            paragraphs = paragraph
            
            logging.info(f"Extracted text from chatgpt: {paragraphs}")
            result = "\n\n".join(paragraphs)
            
            # Close the browser window
            time.sleep(1)
            pyautogui.hotkey('alt', 'f4')
            
            if not result or result.strip() == "":
                self.jarvis.ask_chatgpt(query)
                return True
                # return "Unable to extract text from ChatGPT page. See screenshot for details."
                
            return result
            
        except Exception as e:
            error_details = f"Failed with PyAutoGUI mouse approach: {str(e)}"
            logging.error(error_details)
            
            # Try to close any open browser window even if we had an error
            try:
                pyautogui.hotkey('alt', 'f4')
            except:
                pass
                
            return error_details

    def search_perplexity(self, query):
        logging.info("Using PyAutoGUI with mouse movements to access Perplexity...")
        try:
            import pyautogui
            import time
            import os
            import pyperclip
            import random
            
            # Get screen dimensions
            screen_width, screen_height = pyautogui.size()
            center_x, center_y = screen_width // 2, screen_height // 2
            
            # Open a browser window (this assumes you have Chrome installed)
            os.system('start chrome --new-window "https://perplexity.ai"')
            time.sleep(5)  # Wait for browser to open
            
            # Navigate to search
            pyautogui.hotkey('ctrl', 'l')  # Focus address bar
            time.sleep(0.5)
            pyperclip.copy(f"https://perplexity.ai/search?q={urllib.parse.quote(query)}")
            pyautogui.hotkey('ctrl', 'v')  # Paste URL
            time.sleep(0.3)
            pyautogui.press('enter')
            time.sleep(12)  # Wait for page to load
            
            # Add human-like mouse movement - move to center of screen with slight randomization
            target_x = center_x + random.randint(-50, 50)
            target_y = center_y + random.randint(-50, 50)
            
            # Move mouse smoothly to simulate human movement
            pyautogui.moveTo(target_x, target_y, duration=1.5)
            time.sleep(0.5)
            
            # Click to ensure focus is on the content area
            pyautogui.click()
            time.sleep(1)
            
            # Scroll down a bit to see more content
            for _ in range(2):
                pyautogui.scroll(-300)  # Scroll down
                time.sleep(random.uniform(0.5, 1.2))
            
            # Take a screenshot to verify what we're seeing
            screenshot = pyautogui.screenshot()
            screenshot_path = f"perplexity_screenshot_{int(time.time())}.png"
            screenshot.save(screenshot_path)
            logging.info(f"Screenshot saved to {screenshot_path}")
            
            # Move to an area likely to contain text (slightly below center)
            text_area_x = center_x + random.randint(-100, 100)
            text_area_y = center_y + random.randint(50, 150)  # Below center where content likely is
            
            pyautogui.moveTo(text_area_x, text_area_y, duration=1.0)
            time.sleep(0.3)
            
            # Triple-click to select a paragraph of text
            pyautogui.tripleClick()
            time.sleep(0.3)
            
            # Copy the selected text
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.5)
            paragraph = pyperclip.paste()
            
            # Combine unique paragraphs (avoid duplicates)
            paragraphs = paragraph
            
            logging.info(f"Extracted text from Perplexity: {paragraphs}")
            result = "\n\n".join(paragraphs) if isinstance(paragraphs, list) else paragraphs
            
            # Close the browser window
            time.sleep(1)
            pyautogui.hotkey('alt', 'f4')
            
            if not result or result.strip() == "":
                return "Unable to extract text from Perplexity page. See screenshot for details."
                
            return result
            
        except Exception as e:
            error_details = f"Failed with PyAutoGUI mouse approach for Perplexity: {str(e)}"
            logging.error(error_details)
            
            # Try to close any open browser window even if we had an error
            try:
                pyautogui.hotkey('alt', 'f4')
            except:
                pass
                
            return error_details

    def scrape_webpage_content(self, url, css_selector=None):
        logging.info("enter In scrape_webpage_content function...")
        try:
            html_content = self.get_webpage(url)
            if not html_content:
                return None
                
            soup = BeautifulSoup(html_content, 'html.parser')
            if css_selector:
                content = soup.select(css_selector)
                return '\n'.join([elem.get_text(strip=True) for elem in content])
            else:
                main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup.find('div', class_='result')
                if main_content:
                    return main_content.get_text(strip=True)
                return soup.get_text(strip=True)
        except Exception as e:
            self.logger.error(f"Error scraping webpage: {e}")
            return None

    def get_youtube_results_list(self, search_query, max_results=10):
        formatted_query = urllib.parse.quote(search_query)
        url = f"https://www.youtube.com/results?search_query={formatted_query}"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9"
        }

        response = requests.get(url, headers=headers)
        match = re.search(r"var ytInitialData = ({.*?});</script>", response.text)

        if not match:
            self.logger.error("Failed to extract video list from YouTube")
            return []

        json_data = json.loads(match.group(1))
        contents = json_data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]\
            ["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"]

        results = []
        for item in contents:
            if "videoRenderer" in item:
                vid = item["videoRenderer"]
                title = vid["title"]["runs"][0]["text"]
                video_id = vid["videoId"]
                url = f"https://www.youtube.com/watch?v={video_id}"
                results.append({"title": title, "url": url})
                if len(results) >= max_results:
                    break

        return results














# local_ai_manager.py
import subprocess
import requests
import json
import logging

class LocalAIManager:
    def __init__(self, model_name="deepseek-r1:1.5b", port=11434):
        self.model_name = model_name
        self.port = port
        self.process = None
        self.base_url = f"http://localhost:{self.port}"
        self.model_initialized = False

    def start_model(self):
        try:
            logging.info(f"Starting local AI model '{self.model_name}' via Ollama...")
            self.process = subprocess.Popen(
                ["ollama", "run", self.model_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logging.info(f"Model '{self.model_name}' started.")
        except Exception as e:
            logging.error(f"Failed to start local model: {e}")

    def query_model(self, prompt):
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model_name, "prompt": prompt},
                stream=True
            )
            if response.ok:
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line.decode("utf-8"))
                        if "response" in chunk:
                            full_response += chunk["response"]
                logging.info(f"Local model response: {full_response}")
                return full_response
            else:
                logging.error(f"Model returned error: {response.text}")
                return None
        except Exception as e:
            logging.error(f"Error querying local model: {e}")
            return None
        

    # Flag to track if model has been checked/started
    


    def start_llava_model(self, model_name="llava:7b"):
        try:
            subprocess.Popen(["ollama", "run", model_name])
            print(f"Starting model {model_name}...")
            time.sleep(5)
        except Exception as e:
            print(f"Failed to start model {model_name}: {e}")

    def ask_llava_about_screenshot(self, prompt_text, model_name="llava:7b", api_url="http://localhost:11434/api/generate"):
        try:
            if not self.model_initialized:
                try:
                    models = requests.get("http://localhost:11434/api/tags", timeout=3).json()
                    model_running = any("llava" in m["name"] for m in models.get("models", []))
                except:
                    model_running = False

                if not model_running:
                    self.start_llava_model(model_name)

                self.model_initialized = True

            # Take screenshot and encode it to base64
            screenshot = ImageGrab.grab()
            buffered = io.BytesIO()
            screenshot.save(buffered, format="PNG")
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')

            # Prepare request payload
            payload = {
                "model": model_name,
                "prompt": prompt_text,
                "images": [base64_image],
                "stream": False
            }

            # Send request to LLaVA
            response = requests.post(api_url, json=payload)
            if response.status_code == 200:
                return response.json()["response"]
            else:
                return f"Error from LLaVA: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Exception occurred: {str(e)}"




    def stop_model(self):
        if self.process:
            logging.info("Terminating local AI model...")
            self.process.terminate()
            self.process.wait()
            logging.info("Local model terminated.")











import tkinter as tk
import math
import time
import random
from threading import Thread, Event
from queue import Queue

class JarvisRingAnimation:
    def __init__(self):
        # Color palette - using striking blues with accents
        self.primary_color = "#00C3FF"      # Bright cyan blue
        self.secondary_color = "#0066FF"    # Medium blue
        self.accent_color = "#FFFFFF"       # White for highlights
        self.bg_color = "#07101E"           # Dark navy blue
        self.particle_colors = ["#00C3FF", "#0066FF", "#FFFFFF", "#87CEFA", "#1E90FF"]
        
        # Animation control variables
        self.intensity = 1.0                # Animation intensity (0.0 to 1.0)
        self.auto_hide = True               # Auto hide when duration expires
        self.fade_speed = 0.5               # Speed of fade in/out (seconds)
        
        # Internal state
        self.root = None
        self.canvas = None
        self.is_running = False
        self.is_visible = False
        self.is_speaking = False
        self.last_update_time = 0
        self.opacity = 0.0
        self.target_opacity = 0.0
        self.particles = []
        self.ring_elements = []
        self.text_elements = []
        
        # Control events and queue for thread-safe operations
        self.stop_event = Event()
        self.command_queue = Queue()
        self.animation_thread = None
        
    def create_window(self):
        """Create the transparent window for animation"""
        self.root = tk.Tk()
        self.root.overrideredirect(True)  # Remove window borders
        self.root.attributes("-topmost", True)  # Keep on top
        self.root.attributes("-alpha", 0.0)  # Start fully transparent
        
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Set window size
        window_size = 500  # Larger canvas for more detail
        x = (screen_width - window_size) // 2
        y = (screen_height - window_size) // 2
        
        self.root.geometry(f"{window_size}x{window_size}+{x}+{y}")
        
        # Create canvas with transparent background
        self.canvas = tk.Canvas(
            self.root, 
            width=window_size, 
            height=window_size, 
            bg=self.bg_color,
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Add event to close on click (for debugging)
        self.canvas.bind("<Button-1>", lambda e: self.hide())
        
        # Make the background transparent for clicks
        self.root.wm_attributes("-transparentcolor", self.bg_color)
    
    def create_particle(self, x, y, angle, speed, size, color, lifespan):
        """Create a single particle with properties"""
        return {
            'x': x, 'y': y,
            'angle': angle,
            'speed': speed,
            'size': size,
            'color': color,
            'life': 1.0,  # Starts at full life
            'lifespan': lifespan,  # How long it lives in seconds
            'id': None  # Will store canvas object id
        }
    
    def update_particle(self, particle, dt):
        """Update particle position and life"""
        # Update life
        particle['life'] -= dt / particle['lifespan']
        
        if particle['life'] <= 0:
            return False  # Particle is dead
        
        # Move particle
        particle['x'] += math.cos(particle['angle']) * particle['speed'] * dt * 60
        particle['y'] += math.sin(particle['angle']) * particle['speed'] * dt * 60
        
        # Adjust opacity based on life
        alpha = int(255 * particle['life'])
        r, g, b = int(particle['color'][1:3], 16), int(particle['color'][3:5], 16), int(particle['color'][5:7], 16)
        color = f"#{r:02x}{g:02x}{b:02x}"
        
        # Update or create the particle on canvas
        size = particle['size'] * particle['life']  # Shrink as it dies
        
        if particle['id'] is not None:
            self.canvas.coords(
                particle['id'],
                particle['x'] - size, particle['y'] - size,
                particle['x'] + size, particle['y'] + size
            )
            self.canvas.itemconfig(particle['id'], fill=color)
        else:
            particle['id'] = self.canvas.create_oval(
                particle['x'] - size, particle['y'] - size,
                particle['x'] + size, particle['y'] + size,
                fill=color, outline=""
            )
            
        return True  # Particle still alive
    
    def create_segment(self, center_x, center_y, radius, start_angle, end_angle, 
                      color, width, progress=1.0, segments=30):
        """Create a segment of the ring with dashed/tech effect"""
        # Calculate points along the arc
        points = []
        angle_step = (end_angle - start_angle) / segments
        
        for i in range(segments + 1):
            if random.random() > 0.8:  # Skip some segments for tech effect
                continue
                
            angle = start_angle + angle_step * i
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points.append((x, y))
        
        # Draw each segment (with varying widths for tech effect)
        segment_ids = []
        for i in range(len(points) - 1):
            if random.random() > progress:  # Progressive appearance
                continue
                
            # Vary width slightly for tech effect
            segment_width = width * (0.5 + random.random())
            
            segment_id = self.canvas.create_line(
                points[i][0], points[i][1], 
                points[i+1][0], points[i+1][1],
                fill=color, width=segment_width, 
                capstyle=tk.ROUND
            )
            segment_ids.append(segment_id)
            
        return segment_ids
    
    def draw_frame(self, dt):
        """Draw a single frame of the animation"""
        # Center point of animation
        center_x = 250
        center_y = 250
        
        # Clean up old elements
        for element in self.ring_elements:
            self.canvas.delete(element)
        self.ring_elements = []
        
        for text in self.text_elements:
            self.canvas.delete(text)
        self.text_elements = []
        
        # Update opacity for fade in/out
        if self.opacity < self.target_opacity:
            self.opacity = min(self.target_opacity, self.opacity + dt / self.fade_speed)
            self.root.attributes("-alpha", self.opacity)
        elif self.opacity > self.target_opacity:
            self.opacity = max(self.target_opacity, self.opacity - dt / self.fade_speed)
            self.root.attributes("-alpha", self.opacity)
            
            # If we've faded out completely, we can return early
            if self.opacity <= 0:
                return
        
        # Update existing particles
        live_particles = []
        for particle in self.particles:
            if self.update_particle(particle, dt):
                live_particles.append(particle)
            else:
                self.canvas.delete(particle['id'])
        self.particles = live_particles
        
        # Add new particles at a rate based on intensity
        particle_chance = 0.3 * self.intensity
        if self.is_speaking:
            particle_chance *= 2  # More particles when speaking
        
        if random.random() < particle_chance:
            # Calculate a position on the ring
            particle_angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(95, 105)
            
            # Create the particle
            x = center_x + radius * math.cos(particle_angle)
            y = center_y + radius * math.sin(particle_angle)
            
            # Random movement away from or along the ring
            movement_angle = particle_angle + random.uniform(-0.5, 0.5)
            speed = random.uniform(0.05, 0.3) * self.intensity
            size = random.uniform(1, 3)
            color = random.choice(self.particle_colors)
            lifespan = random.uniform(0.5, 1.5)
            
            particle = self.create_particle(x, y, movement_angle, speed, size, color, lifespan)
            self.particles.append(particle)
        
        # Calculate ring pulse based on intensity and speaking state
        pulse_intensity = self.intensity
        if self.is_speaking:
            # More dynamic movement when speaking
            pulse_intensity *= 1.5
            pulse_frequency = 10 + random.uniform(-2, 2)  # Varied frequency
        else:
            # Subtle movement when idle
            pulse_frequency = 5
        
        # Main outer ring
        outer_radius = 100 + 5 * math.sin(time.time() * pulse_frequency) * pulse_intensity
        segments = self.create_segment(
            center_x, center_y, outer_radius, 
            0, 2 * math.pi, 
            self.primary_color, 4, 1.0
        )
        self.ring_elements.extend(segments)
        
        # Inner ring (smaller, different color)
        inner_radius = 90 + 3 * math.sin(time.time() * (pulse_frequency + 2) + 1) * pulse_intensity
        segments = self.create_segment(
            center_x, center_y, inner_radius, 
            0.1, 2 * math.pi - 0.1,  # Offset for effect
            self.secondary_color, 2, 1.0
        )
        self.ring_elements.extend(segments)
        
        # Accent highlights
        for i in range(8):
            highlight_angle = i * math.pi / 4 + time.time() * 0.5 * self.intensity
            highlight_x = center_x + outer_radius * math.cos(highlight_angle)
            highlight_y = center_y + outer_radius * math.sin(highlight_angle)
            
            # Dot at the angle
            dot_id = self.canvas.create_oval(
                highlight_x - 3, highlight_y - 3,
                highlight_x + 3, highlight_y + 3,
                fill=self.accent_color, outline=""
            )
            self.ring_elements.append(dot_id)
        
        # Add text elements if speaking
        if self.is_speaking:
            # System status
            system_text = self.canvas.create_text(
                center_x, center_y - outer_radius - 30,
                text="SYSTEM ACTIVE",
                fill=self.primary_color,
                font=("Courier", 12, "bold")
            )
            self.text_elements.append(system_text)
            
            # Processing text
            processing_text = self.canvas.create_text(
                center_x, center_y + outer_radius + 30,
                text="PROCESSING...",
                fill=self.primary_color,
                font=("Courier", 12)
            )
            self.text_elements.append(processing_text)
    
    def animation_loop(self):
        """Main animation loop that runs in a separate thread"""
        last_frame_time = time.time()
        
        while not self.stop_event.is_set():
            current_time = time.time()
            dt = current_time - last_frame_time
            last_frame_time = current_time
            
            # Process any pending commands from the queue
            while not self.command_queue.empty():
                command, args, kwargs = self.command_queue.get()
                command(*args, **kwargs)
            
            # Schedule the frame draw in the main thread
            if self.root:
                self.root.after(0, self._draw_frame_safe, dt)
            
            # Control frame rate
            time.sleep(0.016)  # ~60fps
    
    def _draw_frame_safe(self, dt):
        """Thread-safe wrapper for draw_frame"""
        try:
            self.draw_frame(dt)
        except Exception as e:
            print(f"Error drawing frame: {e}")
    
    def _execute_in_main_thread(self, command, *args, **kwargs):
        """Execute a command in the main thread"""
        self.command_queue.put((command, args, kwargs))
    
    def start(self):
        """Start the animation system"""
        if self.is_running:
            return
            
        self.create_window()
        self.is_running = True
        self.stop_event.clear()
        
        # Start animation in a separate thread
        self.animation_thread = Thread(target=self.animation_loop)
        self.animation_thread.daemon = True
        self.animation_thread.start()
        
        # Start the main Tkinter loop
        self.root.mainloop()
    
    def stop(self):
        """Stop the animation system completely"""
        self.stop_event.set()
        self.is_running = False
        self.is_visible = False
        
        if self.root:
            try:
                self.root.after(0, self.root.quit)
            except:
                pass
    
    def show(self, duration=None):
        """Show the animation with optional auto-hide duration"""
        if not self.is_running:
            return
            
        self._execute_in_main_thread(self._show, duration)
    
    def _show(self, duration=None):
        """Actual show implementation (runs in main thread)"""
        self.target_opacity = 0.95
        self.is_visible = True
         # Temporarily increase intensity for visible pulsation
        if not self.is_speaking:
            self.intensity = 1.2  # Or any suitable higher default
            self.root.after(3000, lambda: self._set_intensity(1.2))
        
        # If duration is provided, schedule a hide
        if duration is not None and self.auto_hide:
            self.root.after(int(duration * 1000), self._hide_if_not_speaking)
    
    def _hide_if_not_speaking(self):
        """Hide if not speaking (runs in main thread)"""
        if self.is_visible and not self.is_speaking:
            self.hide()
    
    def hide(self):
        """Hide the animation (fade out)"""
        self._execute_in_main_thread(self._hide)
    
    def _hide(self):
        """Actual hide implementation (runs in main thread)"""
        self.target_opacity = 0.0
        self.is_visible = False
    
    def set_speaking(self, is_speaking):
        """Set whether JARVIS is currently speaking"""
        self._execute_in_main_thread(self._set_speaking, is_speaking)
    
    def _set_speaking(self, is_speaking):
        """Actual set_speaking implementation (runs in main thread)"""
        self.is_speaking = is_speaking
        
        # Show animation if speaking starts
        if is_speaking:
            self.intensity = 0.5  # Full intensity when speaking
            self.show()
        else:
            # Reduce intensity when not speaking
            self.intensity = 0.3
            
            # If auto-hide is enabled, hide after 3 seconds
            if self.auto_hide:
                self.root.after(3000, self._hide_if_not_speaking)
    
    def set_intensity(self, intensity):
        """Set the animation intensity (0.0 to 1.0)"""
        self._execute_in_main_thread(self._set_intensity, intensity)
    
    def _set_intensity(self, intensity):
        """Actual set_intensity implementation (runs in main thread)"""
        self.intensity = max(0.0, min(1.0, intensity))


def example_jarvis_integration():
    # Step 1: Create the animation instance
    animation = JarvisRingAnimation()

    # Step 2: Start animation system in background thread
    animation_thread = Thread(target=animation.start, daemon=True)
    animation_thread.start()

    

    # Step 3: Wait for Tkinter to be ready
    def wait_until_ready():
        while animation.root is None:
            time.sleep(0.05)

        # Once ready, schedule animation actions
        def after_ready():
            print("JARVIS activated")
            animation.show()
            animation.set_speaking(True)

            # After 3 seconds, stop speaking
            animation.root.after(3000, lambda: animation.set_speaking(False))

            # After 5 seconds, hide the ring
            animation.root.after(5000, lambda: animation.hide())

        # Schedule after_ready in the Tkinter main loop
        animation.root.after(0, after_ready)

    Thread(target=wait_until_ready, daemon=True).start()

    # Step 4: Your main thread can do other tasks
    try:
        for i in range(10):
            print("Main program logic running...", i)
            time.sleep(1)

        print("Shutting down JARVIS")
        animation.stop()

    except KeyboardInterrupt:
        animation.stop()

# if __name__ == "__main__":
#     # Run the example
#     example_jarvis_integration()







import speech_recognition as sr
import time
import re

class JarvisListener:
    def __init__(self, wake_word="jarvis"):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.wake_word = wake_word.lower()
        self.local_ai = LocalAIManager()
        

        # Adjust for ambient noise
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
            print("Ambient noise threshold set to {}".format(self.recognizer.energy_threshold))
    
    def listen_for_command(self):
        """Listen continuously until a wake word is detected, then return the command"""
        print("Listening for wake word '{}'...".format(self.wake_word))
        
        while True:
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=None)
                
                try:
                    # Use recognize_google for speech recognition (requires internet)
                    text = self.recognizer.recognize_google(audio).lower()
                    print("Heard: {}".format(text))
                    
                    # Check if wake word is in the text
                    if self.wake_word in text:
                        # Extract command after wake word
                        command = self._extract_command(text)
                        if command:
                            print("Command detected: {}".format(command))
                            return command
                
                except sr.UnknownValueError:
                    # Speech was unintelligible
                    pass
                except sr.RequestError as e:
                    print("Could not request results; {0}".format(e))
            
            except KeyboardInterrupt:
                return "exit"
    
    def listen_for_command_with_timeout(self, timeout_seconds):
        """Listen for wake word with a timeout period"""
        print(f"Listening for wake word '{self.wake_word}' (timeout: {timeout_seconds}s)...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                with self.microphone as source:
                    try:
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                    except sr.WaitTimeoutError:
                        # No speech detected within timeout window, continue loop
                        continue

                
                try:
                    # Use recognize_google for speech recognition
                    text = self.recognizer.recognize_google(audio).lower()
                    print("Heard: {}".format(text))
                    
                    # Check if wake word is in the text
                    if self.wake_word in text:
                        # Extract command after wake word
                        command = self._extract_command(text)
                        if command:
                            print("Command detected: {}".format(command))
                            return command
                    elif len(text.strip()) > 0:
                        prompt = (
                            f"You are a smart assistant. The user said: '{text}'. "
                            "Determine if this could be any of the following:\n"
                            "- A command (like 'turn off the lights', 'open Chrome', 'turn on wifi')\n"
                            "- A system request (like 'turn on wifi from settings', 'increase volume', 'restart computer')\n"
                            "- A question (like 'what time is it?', 'how's the weather?')\n"
                            "- A query (like 'tell me about Paris', 'search for pizza recipes')\n"
                            "- Any request that indicates the user wants a response or action\n\n"
                            "Be generous in your interpretation - if there's a reasonable chance the text is meant for you to respond to or take action on, answer TRUE. "
                            "Only answer FALSE if it's clearly just background noise, random words, or clearly not directed at any assistant (like 'hmm', 'let me think', or similar).\n\n"
                            "IMPORTANT: When in doubt, always answer TRUE. It's better to respond unnecessarily than to miss a real command.\n\n"
                            "Respond with JSON like:\n{\"is_valid_input\": true}"
                        )

                        ai_response = self.local_ai.query_model(prompt)
                        try:
                            decision = json.loads(extract_json_block(ai_response))
                            if decision.get("is_valid_input", False):
                                
                                print("Command confirmed by AI without wake word.")
                                return text.strip()
                        except Exception as e:
                            print(f"AI parsing failed: {e}")
                except sr.UnknownValueError:
                    # Speech was unintelligible
                    pass
                except sr.RequestError as e:
                    print("Could not request results; {0}".format(e))
                except sr.WaitTimeoutError:
                    # Timeout on listen, continue loop to check overall timeout
                    pass
            
            except KeyboardInterrupt:
                return "exit"
            
            # Calculate remaining time and show update every 2 seconds
            elapsed = time.time() - start_time
            if int(elapsed) % 2 == 0 and int(elapsed) != int(elapsed - 0.1):
                remaining = max(0, timeout_seconds - elapsed)
                print(f"Waiting for command... {int(remaining)}s remaining", end="\r")
        
        print("\nTimeout reached. No command detected.")
        return None
    
    def _extract_command(self, text):
        """Extract the command part after the wake word"""
        # Using regex to find all occurrences of wake word
        pattern = r'{}(.+)'.format(self.wake_word)
        match = re.search(pattern, text)
        
        if match:
            # Return the text after the wake word, stripped of leading/trailing spaces
            return match.group(1).strip()
        
        # If wake word is at the end with no command
        if text.strip().endswith(self.wake_word):
            return ""
            
        # Check if wake word is at the beginning
        if text.strip().startswith(self.wake_word):
            # Return everything after the wake word
            return text.replace(self.wake_word, "", 1).strip()
            
        return None



def remove_thinking_tags(self, text):
        """
        Remove <think>...</think> tags from DeepSeek R1 model output.
        
        Args:
            text (str): The raw text output from the model
            
        Returns:
            str: Cleaned text without thinking tags
        """
        if not text:
            return text
            
        # Simple regex approach to remove everything between and including <think> tags
        import re
        cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # Alternative approach: find everything between tags if regex fails
        if '<think>' in cleaned_text or '</think>' in cleaned_text:
            try:
                # Manual extraction approach as fallback
                start_idx = text.find('<think>')
                if start_idx != -1:
                    end_idx = text.find('</think>', start_idx)
                    if end_idx != -1:
                        # Remove the tagged section including the tags
                        cleaned_text = text[:start_idx] + text[end_idx + len('</think>'):]
            except Exception as e:
                logging.warning(f"Error in manual thinking tag removal: {str(e)}")
        
        # Clean up any potential double spaces or extra line breaks from removal
        cleaned_text = re.sub(r'\n\s*\n', '\n\n', cleaned_text)
        cleaned_text = re.sub(r' +', ' ', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        return cleaned_text



        


if __name__ == "__main__":
    main()
    # example_jarvis_integration()
