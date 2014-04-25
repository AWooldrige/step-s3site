test:: flake8 venv
	. venv/bin/activate && nosetests tests

flake8:: venv
	. venv/bin/activate && flake8 *.py tests/*.py

venv: venv/bin/activate
venv/bin/activate: requirements.txt
	dpkg -s python-virtualenv || sudo apt-get install -y python-virtualenv
	test -d venv || virtualenv --no-site-packages venv
	. venv/bin/activate && pip install -r requirements.txt
	touch venv/bin/activate

clean::
	rm -rf venv
