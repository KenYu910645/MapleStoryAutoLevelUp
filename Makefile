PYTHON=python3
VENV=venv
ACTIVATE=. $(VENV)/bin/activate

.PHONY: setup clean run

setup:
	$(PYTHON) -m venv $(VENV)
	$(ACTIVATE); pip install --upgrade pip
	$(ACTIVATE); pip install -r requirements.txt

clean:
	rm -rf $(VENV)

run-fire-land-2:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map fire_land_2 --monsters fire_pig,black_axe_stump --attack directional --cfg=gun
run-ant-cave-2:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map ant_cave_2 --monsters spike_mushroom,zombie_mushroom --attack directional --cfg=gun
run-cloud-balcony:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map cloud_balcony --monsters brown_windup_bear,pink_windup_bear --attack directional --cfg=gun
run-north-forest-training-ground-2:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map north_forest_training_ground_2 --monsters green_mushroom,spike_mushroom --attack directional --cfg=gun
run-lost-time-1:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map lost_time_1 --monsters evolved_ghost --attack directional --cfg=gun
run-north-forest-training-ground-8:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map north_forest_training_ground_8 --monsters wind_single_eye_beast --attack directional --cfg=gun
run-monkey-swamp-3:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map monkey_swamp_3 --monsters angel_monkey --attack aoe_skill --cfg=gun
run-garden-of-red-2:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map garden_of_red_2 --monsters red_cellion --attack directional --cfg=gun
