import time
from io import BytesIO

import requests
from PIL import Image
from playwright.sync_api import sync_playwright
from ultralytics import YOLO


def run_recaptcha_solver():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport=None)
        page = context.new_page()
        try:
            page.goto('https://www.google.com/recaptcha/api2/demo')
            print('Halaman demo dibuka')
            recaptcha_frame = next((frame for frame in page.frames
                                    if frame.url and 'recaptcha/api2/anchor' in frame.url), None)
            if recaptcha_frame:
                checkbox = recaptcha_frame.wait_for_selector('.recaptcha-checkbox-border')
                checkbox.click()
                print('Checkbox diklik')
                page.wait_for_selector('iframe[title="recaptcha challenge expires in two minutes"]',
                                       timeout=10000)
                challenge_frame = next((frame for frame in page.frames if 'bframe' in frame.url), None)
                if challenge_frame:
                    solve_challenge(challenge_frame)
            time.sleep(5)
        except Exception as e:
            print(f'Terjadi kesalahan: {e}')
        finally:
            browser.close()


def solve_challenge(frame):
    # Load model once
    try:
        model = YOLO("yolov8s.pt")
        print("Model loaded successfully")
    except Exception as e:
        print(f"Error loading model: {e}")
        return False

    # Keep solving until complete or max retries
    max_attempts = 20
    attempts = 0

    while attempts < max_attempts:
        attempts += 1
        print(f"Attempt {attempts}/{max_attempts}")

        # First check if frame is still attached - this would indicate success
        try:
            # Check if parent page shows reCAPTCHA as verified
            parent_page = frame.page
            recaptcha_success = parent_page.evaluate('''
                () => {
                    // Check if g-recaptcha-response has content or recaptcha anchor is marked as checked
                    const response = document.querySelector('.g-recaptcha-response');
                    if (response && response.value.length > 0) return true;

                    // Check if demo shows success message
                    const successText = document.body.textContent;
                    return successText && (
                        successText.includes('Verification Success') || 
                        successText.includes('Verification successful')
                    );
                }
            ''')

            if recaptcha_success:
                print("CAPTCHA SOLVED! Verification success detected on parent page.")
                return True

            # Check if frame is still attached
            if not is_frame_attached(frame):
                print("CAPTCHA SOLVED! Challenge frame no longer exists.")
                return True

            # Continue with normal flow...
            target_object = frame.evaluate('''
                () => {
                    const strong = document.querySelector('.rc-imageselect-desc-wrapper strong');
                    return strong ? strong.innerText.trim() : null;
                }
            ''')
            print(f"Target objek: {target_object}")

            # Rest of your existing logic...
            grid_info = frame.evaluate('''
                () => {
                    return {
                        isSingleImage: !!document.querySelector('.rc-imageselect-table-44') ||
                                      !!document.querySelector('.rc-imageselect-table-33'),
                        gridType: document.querySelector('.rc-imageselect-table-44') ? '4x4' : '3x3'
                    };
                }
            ''')
            print(f"Grid type: {grid_info['gridType']}")

            # Get image data...
            image_data = frame.evaluate('''
                () => {
                    const tiles = Array.from(document.querySelectorAll('.rc-imageselect-tile'));
                    const tileImages = tiles.map(tile => {
                        const img = tile.querySelector('img');
                        return img ? img.src : null;
                    });
                    const singleImage = document.querySelector('.rc-image-tile-44') ||
                                      document.querySelector('.rc-image-tile-33');
                    const mainImageSrc = singleImage ? singleImage.src : null;
                    return {
                        tileImages: tileImages,
                        mainImageSrc: mainImageSrc
                    };
                }
            ''')

            # Process images and handle clicking
            # If many timeout errors happen, it's likely the CAPTCHA is solved
            try:
                if detect_and_solve(frame, image_data, grid_info, target_object, model):
                    print("CAPTCHA SOLVED during detection/solving!")
                    return True

                # Check for timeout errors that might indicate success
                time.sleep(2)
            except Exception as process_error:
                if "Timeout" in str(process_error):
                    print("Multiple timeouts detected, checking if CAPTCHA is solved...")
                    time.sleep(3)

                    # Check if parent frame indicates success
                    try:
                        if not is_frame_attached(frame) or parent_page.evaluate(
                                '() => document.querySelector(".recaptcha-success")'):
                            print("CAPTCHA appears to be solved after timeouts!")
                            return True
                    except:
                        pass

            # Check for error messages
            try:
                # Check if frame is still attached after processing
                if not is_frame_attached(frame):
                    print("CAPTCHA SOLVED after processing! Frame detached.")
                    return True

                error_message = frame.evaluate('''
                    () => {
                        const errorDynamic = document.querySelector('.rc-imageselect-error-dynamic-more');
                        const errorSelectMore = document.querySelector('.rc-imageselect-error-select-more');
                        if (errorDynamic && errorDynamic.style.display !== 'none') {
                            return 'dynamic';
                        } else if (errorSelectMore && errorSelectMore.style.display !== 'none') {
                            return 'more';
                        } else {
                            const verifyButton = document.querySelector('#recaptcha-verify-button');
                            if (!verifyButton) return 'success';
                            return 'continue';
                        }
                    }
                ''')
                print(f"Status: {error_message}")

                if error_message == 'success':
                    print("reCAPTCHA solved successfully!")
                    return True

            except Exception as e:
                if "Frame was detached" in str(e) or "Element is not attached" in str(e):
                    print("CAPTCHA SOLVED during status check!")
                    return True

        except Exception as e:
            if any(x in str(e) for x in ["Frame was detached", "Element is not attached", "Timeout"]):
                print(f"CAPTCHA likely SOLVED! Error: {str(e)}")
                time.sleep(2)
                return True
            else:
                print(f"Error during challenge: {e}")
                time.sleep(1)

    print("Maximum attempts reached without solving the reCAPTCHA")
    return False

def is_frame_attached(frame):
    """Check if a frame is still attached to the DOM"""
    try:
        # Try a simple evaluation that should work on any attached frame
        frame.evaluate('() => document.readyState')
        return True
    except Exception:
        return False

def detect_and_solve(frame, image_data, grid_info, target_object, model):
    print(f"Mencari objek: {target_object}")

    # Map common reCAPTCHA objects to COCO classes
    target_mapping = {
        "crosswalks": "crosswalk",
        "crosswalk": "crosswalk",
        "bicycles": "bicycle",
        "bicycle": "bicycle",
        "traffic lights": "traffic light",
        "traffic light": "traffic light",
        "cars": "car",
        "car": "car",
        "buses": "bus",
        "bus": "bus",
        "fire hydrants": "fire hydrant",
        "fire hydrant": "fire hydrant",
        "stairs": "stair",
        "motorcycles": "motorcycle",
        "motorcycle": "motorcycle",
        "bridges": "bridge",
        "bridge": "bridge",
    }

    # Try mapped target first, fallback to original
    search_target = target_mapping.get(target_object, target_object)

    set()

    if grid_info['isSingleImage']:
        cells_to_click = process_single_image(model, image_data['mainImageSrc'], grid_info, search_target)
    else:
        cells_to_click = process_multiple_images(model, image_data['tileImages'], search_target)

    # If no objects found, check if we should skip
    if not cells_to_click:
        print("No matching objects found, checking if we should skip")
        button_text = frame.evaluate('''
            () => {
                const button = document.querySelector('#recaptcha-verify-button');
                return button ? button.innerText.trim().toLowerCase() : '';
            }
        ''')

        print(f"Verify button text: {button_text}")

        if button_text in ['skip', 'lewati', 'lompati']:
            print("Clicking Skip button")
            verify_button = frame.query_selector('#recaptcha-verify-button')
            if verify_button:
                verify_button.click()
        else:
            print("No objects found but button is not skip - waiting for next instruction")
    else:
        # Objects found, click them as normal
        print(f"Sel yang akan diklik: {cells_to_click}")
        safe_click_cells(frame, cells_to_click)


def process_single_image(model, image_url, grid_info, target):
    img = download_image(image_url)
    if img is None:
        return set()

    # Use YOLO model for detection
    results = model(img)

    # Get detected classes
    detected_classes = [model.names[int(cls)] for cls in results[0].boxes.cls.cpu().numpy()]
    print(f"Detected classes: {set(detected_classes)}")

    # Set up grid dimensions
    rows, cols = (4, 4) if grid_info['gridType'] == '4x4' else (3, 3)
    img_width, img_height = img.size
    cell_width = img_width / cols
    cell_height = img_height / rows

    cells_to_click = set()
    overlap_threshold = 0.10  # Cell must contain at least 10% of object

    # Find all boxes for the target class
    for box, cls_id in zip(results[0].boxes.xyxy, results[0].boxes.cls):
        detected_class = model.names[int(cls_id)]
        if target in detected_class or detected_class in target:
            x1, y1, x2, y2 = box.cpu().numpy()
            box_area = (x2 - x1) * (y2 - y1)

            # Check each cell for significant overlap
            for row in range(rows):
                for col in range(cols):
                    # Calculate cell boundaries
                    cell_x1 = col * cell_width
                    cell_y1 = row * cell_height
                    cell_x2 = (col + 1) * cell_width
                    cell_y2 = (row + 1) * cell_height

                    # Calculate intersection
                    intersect_x1 = max(cell_x1, x1)
                    intersect_y1 = max(cell_y1, y1)
                    intersect_x2 = min(cell_x2, x2)
                    intersect_y2 = min(cell_y2, y2)

                    # Check if there's an actual intersection
                    if intersect_x2 > intersect_x1 and intersect_y2 > intersect_y1:
                        # Calculate intersection area
                        intersect_area = (intersect_x2 - intersect_x1) * (intersect_y2 - intersect_y1)
                        cell_area = cell_width * cell_height

                        # Calculate coverage percentage (two ways to look at it)
                        cell_coverage = intersect_area / cell_area
                        object_coverage = intersect_area / box_area

                        # Use the higher of the two metrics to determine if we should click
                        if max(cell_coverage, object_coverage) > overlap_threshold:
                            cell_idx = row * cols + col
                            cells_to_click.add(cell_idx)
                            print(f"Selected cell {cell_idx}: {max(cell_coverage, object_coverage):.2f} overlap")

    return cells_to_click

def process_multiple_images(model, image_urls, target):
    cells_to_click = set()

    for idx, url in enumerate(image_urls):
        if url:
            img = download_image(url)
            if img is None:
                continue

            # Use YOLO for object detection
            results = model(img)

            # Check if target appears in detected classes
            has_target = False
            detected_classes = [model.names[int(cls)] for cls in results[0].boxes.cls.cpu().numpy()]

            for detected_class in detected_classes:
                if target in detected_class or detected_class in target:
                    has_target = True
                    break

            if has_target:
                print(f"Gambar {idx}: {target} terdeteksi")
                cells_to_click.add(idx)

    return cells_to_click


def download_image(url):
    try:
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        return img
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None


def safe_click_cells(frame, cell_indices):
    try:
        all_tiles = frame.query_selector_all('.rc-imageselect-tile')
        print(f"Total tiles ditemukan: {len(all_tiles)}")

        for idx in sorted(cell_indices):
            if idx < len(all_tiles):
                print(f"Clicking cell {idx}")
                all_tiles[idx].click()
                time.sleep(0.3)
            else:
                print(f"Cell {idx} di luar range (max: {len(all_tiles) - 1})")

        if cell_indices:
            verify_button = frame.query_selector('#recaptcha-verify-button')
            if verify_button:
                print("Clicking verify button")
                verify_button.click()
            else:
                print("Verify button tidak ditemukan")
    except Exception as e:
        print(f"Error saat klik: {e}")


if __name__ == "__main__":
    run_recaptcha_solver()
