.PHONY: test check

test:
	python3 -m unittest discover -s tests -v

check: test
	python3 -m py_compile speed_test.py
	python3 speed_test.py --help >/dev/null
