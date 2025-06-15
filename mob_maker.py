import requests
import json
import cv2
import numpy as np

# Assuming a base URL for the API. In a real application, this would be in a config file.
BASE_URL = "https://maplestory.io/" # Placeholder URL, replace with actual API base URL

# Default region and version if not provided
DEFAULT_REGION = "GMS"
DEFAULT_VERSION = "65"

def get_all_mobs(region=None, version=None):
    """
    Fetches world map data from the MapleStory API.

    Args:
        region (str, optional): The region of the map (e.g., "KMS", "GMS"). Defaults to DEFAULT_REGION.
        version (str, optional): The API version. Defaults to DEFAULT_VERSION.

    Returns:
        dict or None: A dictionary containing the world map data if successful, None otherwise.
    """
    if region is None:
        region = DEFAULT_REGION
    if version is None:
        version = DEFAULT_VERSION

    url = f"{BASE_URL}/api/{region}/{version}/mob"
    print(f"Fetching mobs from: {url}")

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.json()
    
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"An unexpected error occurred: {req_err}")
    except json.JSONDecodeError:
        print(f"Failed to decode JSON from response: {response.text}")
    return None

def find_mob_id(all_mobs, mob_name):
    """
    Finds a monster by name in all mobs data.
    """
    result = next((mob for mob in all_mobs if mob["name"] == mob_name), None)
    if result != None:
        return result['id']
    else:
        return None

def save_mob(mob_id, mob_name="mob"):
    for action in ['stand', 'move']:
        for frame in [0,1]:
            filename = f"{mob_name}_{action}_{frame}.png"
            try:
                response = requests.get(f"{BASE_URL}/api/{DEFAULT_REGION}/{DEFAULT_VERSION}/mob/{mob_id}/render/{action}/{frame}", stream=True)
                response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
                
                # Check if the content type is indeed image/png
                if 'image/png' in response.headers.get('Content-Type', ''):
                    image_data = response.content
                    # Convert image data to a numpy array
                    np_arr = np.frombuffer(image_data, np.uint8)
                    img = cv2.imdecode(np_arr, cv2.IMREAD_UNCHANGED)

                    if img is not None:
                        # Check if the image has an alpha channel (4 channels: B, G, R, A)
                        if img.shape[2] == 4:
                            # Create a mask for transparent pixels (alpha channel is 0)
                            alpha_channel = img[:, :, 3]
                            transparent_pixels = alpha_channel == 0

                            # Set the BGR channels of transparent pixels to green (0, 255, 0)
                            # OpenCV uses BGR format by default
                            img[transparent_pixels] = [0, 255, 0, 255] # Blue, Green, Red, Alpha (set alpha to 255 for opaque green)

                        cv2.imwrite(filename, img)
                        print(f"PNG image successfully downloaded, processed, and saved as {filename}")
                    else:
                        print(f"Failed to decode image from response for {filename}")
                else:
                    print(f"The response content type is not image/png. It is: {response.headers.get('Content-Type')}")
                    print("Response content (first 500 bytes):", response.content[:500])
            except requests.exceptions.RequestException as e:
                print(f"An error occurred while fetching or processing {filename}: {e}")
            except Exception as e: # Catch any other unexpected errors during image processing
                print(f"An unexpected error occurred during image processing for {filename}: {e}")

if __name__ == "__main__":
    mobs = get_all_mobs(region=DEFAULT_REGION, version=DEFAULT_VERSION)
    mob_name = input("Enter mob name: ")
    mob_id = find_mob_id(mobs, mob_name)

    mob_file_name = ""
    for i, text in enumerate(mob_name.split()):
        mob_file_name += text.lower()
        if (i+1) != len(mob_name.split()):
            mob_file_name += '_'
            
    save_mob(mob_id, "monster/" + mob_file_name)
