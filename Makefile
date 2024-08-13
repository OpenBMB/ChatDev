minor_release:
	git flow release start $$(git describe --tags --abbrev=0 | awk -F'[v.]' '{print $$2"."$$3+1".0"}').$$(date +'_%Y-%m-%d')

patch_release:
	git flow release start $$(git describe --tags --abbrev=0 | awk -F'[v.]' '{print $$2"."$$3"."$$4+1}').$$(date +'_%Y-%m-%d')

major_release:
	git flow release start $$(git describe --tags --abbrev=0 | awk -F'[v.]' '{print $$2+1".0.0"}').$$(date +'_%Y-%m-%d')

release_finish:
	git flow release finish "$$(git branch --show-current | sed 's/release\///')" && git push origin develop && git push origin main && git push --tags
