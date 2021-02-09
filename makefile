init:
	echo "init"

build:
	pip install 'twine>=1.5.0'
	python setup.py sdist bdist_wheel

publish:
	pip install 'twine>=1.5.0'
	python setup.py sdist bdist_wheel
	twine upload --skip-existing dist/*
	rm -fr build .egg pycloudxns.egg-info
