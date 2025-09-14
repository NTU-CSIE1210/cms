#include <iostream>

static_assert(__cplusplus == 202302L, "C++23 expected");

int main() {
    int n;
    std::cin >> n;
    std::cout << "correct " << n << std::endl;
}
