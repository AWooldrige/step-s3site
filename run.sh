#!/bin/sh
cd $WERCKER_STEP_ROOT
make venv
source venv/bin/activate
python s3sitedeploy.py
