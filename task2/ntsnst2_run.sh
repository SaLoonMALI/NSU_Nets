git clone https://github.com/SaLoonMALI/testrep
cd testrep
git remote set-url origin git@github.com:SaLoonMALI/testrep.git
touch aaa.ttt && echo "qwertyuo123467" >> aaa.ttt
git add aaa.ttt
git commit -m "add aaa.ttt"
git push origin main
#
