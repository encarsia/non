WHAT IS THIS?

 * a simple GTK+ tool for keeping an eye on your Nikola powered website
 
WHAT CAN I DO WITH IT?

 * have an overview of posts, pages, listings, images, files and translations
 * open files from app
 * keep track of changes made since last build (hint: **bold**)
 * create new posts
 * build, preview and deploy to GitHub or GitLab or a custom target¹
 * create translation file on right click in the 'Translation' tab
 * bookmark and switch between different Nikola site instances
 * integrated terminal for switching easily between GUI and commandline interface

¹ For deploying to GitLab the `nikola github_deploy` command is used. See this [Example Nikola site using GitLab Pages](https://gitlab.com/pages/nikola) for details on how to setup your Nikola configuration. The second "Deploy" toolbutton is active if you setup `DEPLOY_COMMANDS` in your `conf.py` and will execute the _default_ preset.

WHAT CAN'T I DO WITH IT?

 * create a Nikola site
 * pretty much anything else, too

WHAT DO I NEED TO GET IT WORKING?

 * [Nikola](https://getnikola.com/) installation (latest tested version is 7.8.15)
 * configurated Nikola site
 * Python 3 including GObject Introspection bindings

INSTALLATION

 * download and extract or clone repository
 * run `non.py`
 * if you intend to use the desktop icon, edit `non.desktop` and customize real path of "Exec", "Path" and "Icon" and copy file to `~/.local/share/applications/`

THAT SOUNDS PRETTY BASIC. ANY PLANS FOR THE FUTURE ON THIS?

 * My view on this project is quite selfish: I'm trying to improve my skills by writing stuff I intend to use.
 * Besides this there are some ideas for further features such like
    * an integrated ReST editor
    * provide templates

<img src="non_window.png" width="600">
