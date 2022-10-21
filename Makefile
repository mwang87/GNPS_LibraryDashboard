build:
	docker build -t gnpslibrary . 

bash:
	docker run -it --rm gnpslibrary /bin/bash

server-compose-build-nocache:
	docker-compose build --no-cache

server-compose-interactive:
	docker-compose build
	docker-compose --compatibility up

server-compose-develop-mode:
	docker-compose -f docker_develop.yml build
	docker-compose -f docker_develop.yml --compatibility up

server-compose:
	docker-compose build
	docker-compose --compatibility up -d

attach:
	docker exec -i -t gnpslibrary-dash /bin/bash

clear-cache:
	sudo rm temp/* || true
	sudo rm temp/omnisci/data/ -rf || true