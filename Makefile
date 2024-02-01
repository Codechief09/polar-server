start-development:
	pip install isort
	pip install -r requirements.txt
	yarn install
	yarn husky add .husky/pre-commit "yarn lint-staged"
