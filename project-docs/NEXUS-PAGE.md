# Nexus mod page content — Elder Weathers

Everything needed for the Nexus upload form. The description is BBCode, ready
to paste into the mod-page description field.

## Form fields

- **Name**: Elder Weathers
- **Summary** (one line): Original Skyrim weathers generated from a physical
  atmosphere model, not hand-tuned tables. Nineteen weathers across seven
  families, a climate override, and a full Tamriel region pass, as a light
  ESL-flagged plugin.
- **Category**: Weather, Lighting and Effects (or Overhauls)
- **Version**: 1.0.0

## Requirements

- Skyrim Special Edition or Anniversary Edition. The plugin needs no SKSE.
- Works alongside any ENB.

## Description (BBCode)

[size=5]Elder Weathers[/size]

Original Skyrim weathers, generated from a physical sky rather than hand-tuned
tables. A compact atmosphere model fills the full weather color block for
nineteen weathers across seven families, overrides the climate, and
reclassifies every Tamriel weather region onto the authored set, shipping as
one light ESL-flagged plugin (EWWeathers.esp).

[size=4]How the colors are made[/size]

A single-scattering model (a Rayleigh spectrum, a Kasten-Young air mass, and a
turbidity-scaled Mie term) evaluates each archetype at four times of day and
fills the full 17-type weather color block: sky colors, fog planes, cloud
colors, and directional ambient. Seven archetypes span the weather space:
clear, cloudy, overcast, rain, storm, fog, and snow.

Each family then carries variants sampled from the same parameter space, for
nineteen weathers in total: crisp and hazy clears, light and heavy cloud and
rain, a bright overcast, a violent storm, mist and dense fog, light snow and
a blizzard. A variant is not a recolor. It satisfies its family's physics and
sits where its name claims, so a dense fog really does pull the far plane
nearer than a mist, and a blizzard really is darker and windier than light
snow. Both of those are asserted as build invariants.

The model is tested by physical invariant, not by matching known values. The
day sky must be blue-dominant, the sunrise zenith must stay blue while the
sunlight goes warm, night must be far darker than day, overcast must collapse
the direct light, and fog must pull the far plane in. One measure of the
grounding: the clear-sunrise zenith lands within three points per channel of
the value Bethesda's artists tuned by hand, without ever reading it.

[size=4]What is authored and what is inherited[/size]

Every value the model speaks for is generated: the color block, fog, wind, sun
glare, classification flags, lightning color, cloud colors, and directional
ambient. Structural fields the model does not cover (cloud texture paths, layer
alphas, precipitation and visual-effect references, sky statics, image spaces)
are inherited from the matching vanilla weather family by form reference, the
way any plugin references game content. There are no third-party values in the
output.

[size=4]The region pass[/size]

Skyrim distributes most of its weather through region records, so the plugin
overrides every Tamriel-worldspace distribution region (tundra, forests, the
Reach, coast, snow, marsh, and the rest) onto the authored weathers. Each
vanilla weather in a region's list is classified empirically (precipitation
flags, thunder bytes, fog planes, sky spread) and its chance moves to the
matching archetype, so every region keeps its climate character: snowy regions
keep their snow share, rainy coasts keep their rain. FX regions, scripted quest
weathers, and non-Tamriel worldspaces are left untouched byte for byte. City
worldspaces are a later pass.

[size=4]Compatibility and load order[/size]

ESL-flagged and light, so it does not spend a full plugin slot. It overrides
weather, climate, and region distribution, so let it win those records over
other weather mods, or patch between them. It does not touch scripted quest
weathers or non-Tamriel worldspaces.

[size=4]Install[/size]

[list=1]
[*]Install with a mod manager and enable EWWeathers.esp.
[*]Sort your load order.
[*]Load a save outdoors, or wait for the weather to cycle.
[/list]

[size=4]Scope, stated plainly[/size]

In-game visual validation is ahead of this release. The build gates prove
format correctness, physical coherence, and character preservation. They do not
prove it is beautiful. That judgment is yours, and feedback is welcome.

[size=4]Source and license[/size]

MIT licensed. Source and the one-command build are on GitHub.

## Permissions (open, MIT-aligned)

- Users can modify this file: yes
- Users can convert this file to work with other games: yes
- Users can use assets from this file without permission with credit: yes
- Others can use assets in this file with credit, without permission: yes
- Upload to other sites: yes, with credit

State on the page: this mod is MIT licensed; use it, modify it, patch it, and
build weathers on it, with credit.
