# README Review Skill

## Description
Reviews and updates `README.md` to ensure it accurately reflects the current integration logic, entities, blueprints, configuration options, and prerequisites.

## Instructions

### Step 1: Gather current state from source code

Read the following files to build an accurate picture of the integration:

1. `custom_components/offdelay/manifest.json` - version, dependencies, metadata
2. `custom_components/offdelay/const.py` - all constants, enums (HomeStatus, weather ranks, config keys)
3. `custom_components/offdelay/sensor.py` - all sensor entities
4. `custom_components/offdelay/binary_sensor.py` - all binary sensor entities
5. `custom_components/offdelay/switch.py` - all switch entities
6. `custom_components/offdelay/config_flow.py` - configuration options (initial setup + options flow)
7. `custom_components/offdelay/blueprints/automation/*.yaml` - all automation blueprints
8. `custom_components/offdelay/blueprints/script/*.yaml` - all script blueprints

### Step 2: Compare against README.md

Read `README.md` and check each section for accuracy:

1. **Version/badges** - Do badge URLs match the current repo?
2. **Overview description** - Does it accurately describe what the integration does?
3. **Prerequisites** - Are all required integrations and zones listed? Are there any new prerequisites?
4. **Installation** - Are instructions still valid?
5. **Configuration** - Does it list all config options (initial + options flow)? Are defaults correct?
6. **Entities Provided** - Check EVERY entity:
   - Are all sensors listed? Any missing or removed?
   - Are all binary sensors listed? Any missing or removed?
   - Are all switches listed? Any missing or removed?
   - Are entity names, states, and descriptions accurate?
7. **Blueprints** - Are all blueprints documented? Are descriptions accurate?
8. **Testing** - Is the test command still correct?
9. **Troubleshooting** - Are links valid?
10. **License** - Is the license file reference correct?

### Step 3: Update README.md

Apply corrections for any discrepancies found. Rules:
- Keep the existing writing style and tone
- Keep the existing markdown structure and formatting conventions
- Do NOT add AI-generated filler text or unnecessary verbosity
- Do NOT add emojis
- Only change what is factually incorrect or missing
- If an entity was added to the code but is missing from README, add it following the existing format
- If an entity was removed from the code but still in README, remove it
- If configuration options changed, update them
- If blueprints were added/removed, update the blueprints section

### Step 4: Verify

After editing, re-read `README.md` to confirm all changes are correct and the file is well-formed markdown.
