# def hello():
#     print("hello world")

#     hello()
#     hello()

# it is possible to return multiple value? Ans=YES it is possible to return multiple value by using tuple, list, dictionary
# def arithmetic():
#     a = int(input("Enter value of a:"))
#     b = int(input("Enter value of b:"))
#     sum = a+b
#     sub = a-b
#     div = a/b
#     mul = a*b
#     return sum,sub,div,mul

# # print(arithmetic())
# result = arithmetic()
# print("Arithmetic operations are:",result)

#how many types of argument we pass in fucntion? Ans=4 types of argument we can pass in function
# 1. positional argument
# 2. keyword argument
# 3. default argument
# 4. variable length argument/variable number of argument

# def arithmetic(a,b):
#     sum = a+b
#     sub = a-b
#     div = a/b
#     mul = a*b
#     return sum,sub,div,mul
# #positional argument
# result = arithmetic(10,5)
# print("Arithmetic operations are:",result)

# # #keyword argument
# def credentials(username,password):
#     if username == "admin": 
#         print("Login successful")
#     else:
#         print("invalid credetials")    

# credentials(username="admin", password="admin")#calling function by using keyword argument

# #default argument 
# def cityName(city="Pune"):
#     print(city)
    
# cityName("Nagpur")
# cityName("Mumbai")
# cityName()

# #variable length argument/variable number of argument
# def cityName(*name):
#     print(name)
    
# cityName("Nagpur","Mumbai","Pune","Delhi")

def add():
    a = int(input("Enter value of a:"))
    b = int(input("Enter value of b:"))
    print(a+b)

def sub():
    a = int(input("Enter value of a:"))
    b = int(input("Enter value of b:"))
    print(a-b)
        
def mul():
    a = int(input("Enter value of a:"))
    b = int(input("Enter value of b:"))
    print(a*b)

def div():
    a - int(input("Enter value of a:"))
    b = int(input("Enter value of b:"))
    print(a/b)