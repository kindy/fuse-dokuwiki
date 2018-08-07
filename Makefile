
req: env
	. env/bin/activate && pip install  -r requirement.txt

env:
	virtualenv env

loc-doku:
	docker run -d -p 12345:80 --name doku bitnami/dokuwiki