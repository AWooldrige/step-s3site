#!/bin/sh
make venv
source venv/bin/activate
pip install -r requirements.txt
python s3sitedeploy.py
