trait MyTrait:
    fn do_something(self) -> Int:

struct MyStruct:
    var x: Int

impl MyTrait for MyStruct:
    fn do_something(self) -> Int:
        print("MyStruct doing something with", self.x)
        return self.x