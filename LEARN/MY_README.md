# Logs
* 2024.9.5 trying https://medium.com/@meirgotroot/chatdev-review-the-good-the-bad-and-the-ugly-469b5cb691d4
  - After the first generation of AirDefense, the program works quite well except that upon "Game Over", an exception was raised. 
  <pre>
   (most recent call last):
  File "C:\Users\flin\Downloads\AirDefense_DefaultOrganization_20240906045838\main.py", line 60, in <module>
    game.run()
  File "C:\Users\flin\Downloads\AirDefense_DefaultOrganization_20240906045838\main.py", line 25, in run
    self.update()
  File "C:\Users\flin\Downloads\AirDefense_DefaultOrganization_20240906045838\main.py", line 42, in update
    enemy.move()
  File "C:\Users\flin\Downloads\AirDefense_DefaultOrganization_20240906045838\enemy.py", line 16, in move
    self.respawn()
TypeError: Enemy.respawn() missing 1 required positional argument: 'existing_enemies'
  </pre>

# Design Notes
* chatdev is the core folder
* composed_phase.py is about the control on a composition, which contains a number of sub-phases.
* 

# How to run - docker
* https://github.com/aligneddata/ChatDev/blob/main/wiki.md#docker-start

# Build and boot up
<pre>
(ignore the beginning section)

Build Docker images
cd ~/git/ChatDev/
version=$(cat LEARN/DOCKER_BUILD_VER.txt)   # bump it up each time when building
docker build -t chatdev:$version .   

IP=172.25.55.19
docker run -it -v $PWD/LEARN/pub:/pub -p 8123:8000 -e OPENAI_API_KEY=$OPENAI_API_KEY -e DISPLAY=:0 chatdev:$version


</pre>

## Start app from container
<pre>
cd /app
python run.py --model GPT_4O_MINI --task "Create an air defense game using Pygame" --name "AirDefense"

# copy the generated files out
root@9eb011f3c8c5:/app/WareHouse# cp -rp AirDefense_DefaultOrganization_20240906045838/  /pub/
# and use MobaTerm to download to local
# run the generated file from conda 
conda activate main
python main.py
</pre>

## Copy the generated software out of Docker
run
docker cp container_id:/path/in/container /path/on/host

## Access remote browser
* From container: python visualizer/app.py
* From remote: http://172.25.55.19:8123/