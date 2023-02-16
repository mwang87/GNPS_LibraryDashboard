build:
	docker build -t gnpslibrary . 

bash:
	docker run -it --rm gnpslibrary /bin/bash

server-compose-build-nocache:
	docker-compose --compatibility build --no-cache

server-compose-interactive:
	docker-compose --compatibility build
	docker-compose --compatibility up

server-compose-dev:
	docker-compose -f docker-compose.yml -f docker-compose-dev.yml --compatibility build
	docker-compose -f docker-compose.yml -f docker-compose-dev.yml --compatibility up

server-compose:
	docker-compose --compatibility build
	docker-compose --compatibility up -d

server-compose-production:
	docker-compose --compatibility build
	docker-compose --compatibility up -d

attach:
	docker exec -i -t gnpslibrary-dash /bin/bash

clear-cache:
	sudo rm temp/* || true
	sudo rm temp/omnisci/data/ -rf || true