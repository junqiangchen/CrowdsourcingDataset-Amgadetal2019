# -*- coding: utf-8 -*-
"""
Created on Tue Aug  6 13:25:37 2019

@author: tageldim
"""

import os
import sys
CWD = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, CWD)
import logging
logger = logging.getLogger()
import json
import girder_client
import datetime
import wget
from io import BytesIO
from PIL import Image
Image.MAX_IMAGE_PIXELS = 1000000000
import csv

# %%==========================================================
# Params
# ============================================================

APIURL = 'http://demo.kitware.com/histomicstk/api/v1/'
source_folder_id = '5bbdeba3e629140048d017bb'

SAVEPATH = CWD

# %%===========================================================================
# Methods
# =============================================================================

def create_directory_structure(folderList):
    """create folders if non-existent"""
    savepaths = {'base': SAVEPATH}
    for folder in folderList:
        folderpath = os.path.join(SAVEPATH, folder)
        savepaths[folder] = folderpath
        try:
            os.mkdir(folderpath)
        except FileExistsError:
            pass
    return savepaths

def printNlog(msg, level='info'):
  print(msg)
  if level == 'info': 
    logger.info(msg)
  elif level == 'error': 
    logger.error(msg)
  else:
    pass

def get_image_from_htk_response(resp):
    """Given a girder response, get np array image"""        
    image_content = BytesIO(resp.content)
    image_content.seek(0)
    Image.open(image_content)
    image = Image.open(image_content)
    return image

# %%===========================================================================
# Ground work
# =============================================================================

# create directories
savepaths = create_directory_structure(
        ['wsis','annotations','masks','images', 'logs'])

# configure logger
now = str(datetime.datetime.now()).replace(' ', '_').replace(':', '_')
logging.basicConfig(
    filename=os.path.join(savepaths['logs'], now +'.log'), 
    format='%(asctime)s %(levelname)-3s %(message)s', level=logging.INFO)
printNlog("STARTED.")

# Connect to API
#printNlog("""Enter login information below. 
#If you don't have an account, register for free at:
#http://demo.kitware.com/histomicstk/histomicstk
#It only takes a minute.
#""")
gc = girder_client.GirderClient(apiUrl = APIURL)
# gc.authenticate(interactive=True)
gc.authenticate(apiKey='GDetOb3GVvZfMImjPf8lf1yya4dbcaTfDfq9o62v')

# Get list of slides to download
resp = gc.get("item?folderId=%s&limit=1000000" % source_folder_id)
slides = dict()
for s in resp:   
    short_name = s['name'][:12]
    slides[short_name] = {'name': s['name'], '_id': s['_id']}
del resp

# Do not re-download slides 
existing_slides = set([
        j for j in os.listdir(savepaths['wsis']) if j.endswith('.svs')])
slide_list = list(set(slides.keys()) - existing_slides)

# %%===========================================================================
# Create WSI download shell script
# =============================================================================

# bat script if windows, else bash script
ext = '.bat' if os.name == 'nt' else '.sh'
savepaths['wsi_script'] = os.path.join(
    savepaths['wsis'], 'download_wsis' + ext)

# Add commands to batch or bash script
printNlog("Adding download commands to %s" % savepaths['wsi_script'])
resp = gc.post('api_key')
apikey = resp['key']
for slide_name in slide_list:
    command_base = "girder-client --api-url %s --api-key %s download %s %s" % (
            APIURL, apikey, slides[slide_name]['_id'], savepaths['wsis'])
    with open(savepaths['wsi_script'], 'a') as f:
        f.write(command_base + "\n")
    
# %%===========================================================================
# Download JSON annotations
# =============================================================================

for sldid, slide_name in enumerate(slide_list):
    
    printNlog("Downloading annotations: Slide %d of %d (%s)" % (
                sldid+1, len(slide_list), slide_name))
    annotations = gc.get("/annotation/item/" + slides[slide_name]['_id'])
    savename = os.path.join(
            savepaths['annotations'], slides[slide_name]['name'])
    savename = savename.replace('.svs', '.json')
    with open(savename, 'w') as f:
        json.dump(annotations, f)

# %%===========================================================================
# Download all masks
# =============================================================================

printNlog("Downloading masks to %s" % savepaths['masks'])
mask_link = 'https://ndownloader.figshare.com/articles/7193138/versions/1'
wget.download(mask_link, savepaths['masks'])

# %%===========================================================================
# Download RGB images
# =============================================================================

sldid = 0
with open('./roiBounds.csv', newline='') as csvfile:
    reader = csv.DictReader(csvfile)    
    for row in reader:
        
        sldid += 1
        slide_name = row[''][:12]
        
        printNlog("Downloading RGB image: Slide %d of %d (%s)" % (
                sldid+1, len(slide_list), slide_name))
        
        xmin = int(float(row['xmin'])) 
        ymin = int(float(row['ymin']))
        # Get RGB from whol slide
        getStr = "/item/%s/tiles/region?left=%d&right=%d&top=%d&bottom=%d" % (
          slides[slide_name]['_id'], 
          xmin, int(float(row['xmax'])), ymin, int(float(row['ymax'])))
        resp  = gc.get(getStr, jsonResp=False)
        rgb = get_image_from_htk_response(resp)
        # save RGB
        xmin = int(float(row['xmin'])) 
        ymin = int(float(row['ymin']))
        rgb.save(os.path.join(savepaths['images'], "%s_xmin%d_ymin%d_.png" % (
                row[''], xmin, ymin)))
        
# %%===========================================================================
# Done
# =============================================================================
        
printNlog("DONE.")
printNlog("""
Now please run the batch or shell script from the command line using the 
following command:
Windows:
    %s
Mac or Linux:
    bash %s
to download the full whole-slide images.
""" % (savepaths['wsi_script'], savepaths['wsi_script']))
