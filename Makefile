list_commands:
	#Have make automatically list_commands
	echo ""

minor_release:
	git flow release start $$(git describe --tags --abbrev=0 | awk -F'[v.]' '{print $$2"."$$3+1".0"}').$$(date +'_%Y-%m-%d')

patch_release:
	git flow release start $$(git describe --tags --abbrev=0 | awk -F'[v.]' '{print $$2"."$$3"."$$4+1}').$$(date +'_%Y-%m-%d')

major_release:
	git flow release start $$(git describe --tags --abbrev=0 | awk -F'[v.]' '{print $$2+1".0.0"}').$$(date +'_%Y-%m-%d')

release_finish:
	git flow release finish "$$(git branch --show-current | sed 's/release\///')" && git push origin develop && git push origin main && git push --tags

clean_project:
	git clean --exclude=!.env -Xdf

enviroment:
	# make sure that brew is installed and if brew is not installed, install it
	brew --version || /bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
	# make sure that pipenv is installed and if pipenv is not installed, install it
	pipenv --version || pip install pipenv
	# make sure that pyenv is installed and if pyenv is not installed, install it
	pyenv --version || brew install pyenv
	# make sure that you can tab complete make commands and if you can't, setit up
	