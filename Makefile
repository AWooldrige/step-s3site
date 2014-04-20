test:: flake8
	nosetests tests

flake8::
	flake8 *.py tests/*.py

venv:: clean
	virtualenv venv --distribute
	echo "Now run source venv/bin/activate and pip install -r requirements.txt"

clean::
	rm -rf venv
