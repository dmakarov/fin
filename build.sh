~/work/try/llvm/build/bin/clang++ -std=c++11 -c func.cpp -o func.cpp.o
~/work/try/llvm/build/bin/clang++ -std=c++11 -finstrument-functions-after-inlining -o app main.cpp func.cpp.o
rm -f func.cpp.o
