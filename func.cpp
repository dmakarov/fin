#include <atomic>
#include <chrono>
#include <thread>
#include <vector>

#include <fstream>
#include <iomanip>
#include <sstream>

#include <unistd.h>
#include <cxxabi.h>
#include <dlfcn.h>
#include <libproc.h>

extern "C" void __cyg_profile_func_enter(void *this_fn, void *call_site) __attribute__((no_instrument_function));
extern "C" void __cyg_profile_func_exit(void *this_fn, void *call_site) __attribute__((no_instrument_function));

static const auto initial_time = std::chrono::steady_clock::now();

struct instrumentation_event {
    instrumentation_event(int64_t ts, void *fn, bool e) : timestamp(ts), this_fn(fn), entry(e) {}
    int64_t timestamp;
    void *this_fn;
    bool entry;
};

struct call_graph_map {
    std::thread::id tid;
    std::vector<instrumentation_event> events;
    ~call_graph_map()
    {
        if (tid != std::thread::id())
        {
            std::ostringstream oss("pid", std::ios_base::ate);
            oss << getpid() << "thread" << tid << ".trace";
            std::ofstream ofs(oss.str());
            for (auto& e: events)
            {
                int status;
                Dl_info dl_info;
                auto* name = (dladdr(e.this_fn, &dl_info) && dl_info.dli_sname) ? dl_info.dli_sname : "";
                auto* demangled = abi::__cxa_demangle(name, nullptr, nullptr, &status);
                if (status == 0) name = demangled;
                ofs << e.timestamp << (e.entry ? " >> ": " << ") << e.this_fn << " " << name << '\n';
            }
        }
    }
};


constexpr int MAX_THREADS = 100;
call_graph_map the_map[MAX_THREADS];
std::atomic_size_t total_threads{0};
std::atomic_bool instrumentation_disabled(false);

std::vector<instrumentation_event>& find_events()
{
    auto tid = std::this_thread::get_id();
    for (auto it = 0; it != total_threads; ++it)
    {
        if (the_map[it].tid == tid)
        {
            return the_map[it].events;
        }
    }
    auto index = total_threads++;
    the_map[index].tid = tid;
    return the_map[index].events;
}

void __cyg_profile_func_enter(void *this_fn, void *call_site)
{
    using namespace std::chrono;
    if (instrumentation_disabled) return;
    auto diff = duration_cast<microseconds>(steady_clock::now() - initial_time);
    auto& events = find_events();
    events.emplace_back(diff.count(), this_fn, true);
}

void __cyg_profile_func_exit(void *this_fn, void *call_site)
{
    using namespace std::chrono;
    if (instrumentation_disabled) return;
    auto diff = duration_cast<microseconds>(steady_clock::now() - initial_time);
    auto& events = find_events();
    events.emplace_back(diff.count(), this_fn, false);
}
