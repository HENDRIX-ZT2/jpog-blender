## jpog-blender

A toolset for blender allowing the import and export of Jurassic Park - Operation Genesis models, textures and animations.


### Installation
- Click the `Clone or Download` button at the right, then `Download ZIP`.
- Extract the ZIP you just downloaded and pack the _contents_ of the `jpog-blender-master` folder into a new ZIP file.
- To install with the addon installer in Blender, click `File` > `User Preferences` > `Add-ons` > `Install Add-ons from File` and select your new ZIP file.

### Before You Start
- Make sure you gain writing privileges for the JPOG folders.
- Make a backup of your JPOG files, if you haven't already done so.

### How To Use
#### Importing Models
- `File` > `Import` > `Toshi Model (.tmd)`. Import a TMD model from a JPOG-like folder structure, either directly from the game's folders or from a backup. The default settings should be fine. Refer to the tooltips of the import options for further information.
#### Exporting Models
- `File` > `Export` > `Toshi Model (.tmd)`. The default settings should be fine. To export new animations, turn on `Export Anims` and `Pad Anims`.
#### Resizing
- Warning: Needs animations to be exported for ideal results! It will do _something_ without new animations, but won't be perfect.
- Select the armature in object mode, scale it to the desired size and press `Apply Scale to Objects and Animations` in the tool shelf. Export with animations.
#### Custom Animations
- Are theoretically supported, but not tested yet. Edited animations are tested and functional, but under the limitation that _any_ edit of animations breaks the other animals in a dig site. You could replace them with new animals using the new anims. A TKL merger to solve this sort of problems is planned, but not yet started.

### Known Limitations
- Animations break other animals using the same TKL file.

### Credits
- Equinox of https://github.com/OpenJPOG for file format specification and support
- Andres James http://tresed.trescom.org/jpog/ for ConvertCCT source code and original file format specification
- JPOG was created by Blue Tongue Entertainment for Universal Interactive.
