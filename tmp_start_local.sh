docker build -t ptester .
docker run --rm -it -p 8787:5000 -p 5481:5481 -v /home/yves/keys:/app/keys --name PromptTester ptester
