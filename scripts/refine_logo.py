from PIL import Image, ImageChops
import sys
import os

def remove_background_and_crop(input_path, output_path):
    print(f"Processing {input_path}...")
    try:
        img = Image.open(input_path).convert("RGBA")
        datas = img.getdata()
        
        newData = []
        for item in datas:
            # Change all white (also shades of whites) to transparent
            if item[0] > 220 and item[1] > 220 and item[2] > 220:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        
        img.putdata(newData)
        
        # Crop transparent content
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
            print(f"Cropped to {bbox}")
        
        img.save(output_path, "PNG")
        print(f"Saved to {output_path}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python refine_logo.py <path_to_image>")
        sys.exit(1)
        
    input_path = sys.argv[1]
    output_path = sys.argv[1] # Overwrite
    
    remove_background_and_crop(input_path, output_path)
