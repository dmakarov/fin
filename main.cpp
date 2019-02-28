#include <atomic>
#include <iostream>

extern std::atomic_bool instrumentation_disabled;

class Worker
{
public:
    Worker() = default;
    ~Worker() = default;
    void run(int x);
private:
    bool make_decision(int x);
};

void Worker::run(int x)
{
    if (make_decision(x / 2))
    {
        std::cout << "decision is made\n";
        instrumentation_disabled = true;
    }
}

bool Worker::make_decision(int x)
{
    return x % 2 == 0;
}

int main(int argc, char* argv[])
{
    Worker w;
    w.run(8);
    return 0;
}
