-- ============================================
-- 1. DDL - CREACION DE TABLAS
-- ============================================

DROP TABLE IF EXISTS detalle_ventas CASCADE;
DROP TABLE IF EXISTS ventas CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;
DROP TABLE IF EXISTS vendedores CASCADE;
DROP TABLE IF EXISTS productos CASCADE;

CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    dni VARCHAR(8) NOT NULL UNIQUE,
    nombres VARCHAR(150) NOT NULL,
    sexo CHAR(1) NOT NULL CHECK (sexo IN ('M', 'F')),
    fecha_nacimiento DATE NOT NULL
);

CREATE TABLE vendedores (
    id SERIAL PRIMARY KEY,
    dni VARCHAR(8) NOT NULL UNIQUE,
    nombres VARCHAR(150) NOT NULL,
    fecha_ingreso DATE NOT NULL,
    fecha_nacimiento DATE NOT NULL
);

CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    descripcion VARCHAR(200) NOT NULL,
    precio NUMERIC(10,2) NOT NULL CHECK (precio > 0),
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0)
);

CREATE TABLE ventas (
    id SERIAL PRIMARY KEY,
    fecha_venta DATE NOT NULL,
    id_cliente INT NOT NULL REFERENCES clientes(id),
    total_venta NUMERIC(12,2) NOT NULL DEFAULT 0,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('completada', 'pendiente')),
    id_vendedor INT NOT NULL REFERENCES vendedores(id)
);

CREATE TABLE detalle_ventas (
    id SERIAL PRIMARY KEY,
    id_venta INT NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
    id_producto INT NOT NULL REFERENCES productos(id),
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL CHECK (precio_unitario > 0),
    subtotal NUMERIC(12,2) NOT NULL
);

-- ============================================
-- 2. INSERTS - DATA SINTETICA
-- ============================================

-- CLIENTES (20 clientes)
INSERT INTO clientes (dni, nombres, sexo, fecha_nacimiento) VALUES
('71234501', 'Maria Elena Torres Ruiz', 'F', '1990-03-15'),
('71234502', 'Carlos Alberto Mendoza Diaz', 'M', '1985-07-22'),
('71234503', 'Lucia Fernanda Quispe Mamani', 'F', '1992-11-08'),
('71234504', 'Jorge Luis Huaman Flores', 'M', '1988-01-30'),
('71234505', 'Ana Patricia Vargas Lopez', 'F', '1995-06-12'),
('71234506', 'Roberto Daniel Castillo Pena', 'M', '1980-09-25'),
('71234507', 'Carmen Rosa Silva Gutierrez', 'F', '1993-04-18'),
('71234508', 'Diego Fernando Rojas Paredes', 'M', '1991-12-03'),
('71234509', 'Sofia Isabel Navarro Ramos', 'F', '1987-08-14'),
('71234510', 'Miguel Angel Espinoza Cruz', 'M', '1994-02-27'),
('71234511', 'Valentina Paz Herrera Soto', 'F', '1996-10-05'),
('71234512', 'Andres Felipe Morales Vega', 'M', '1983-05-19'),
('71234513', 'Gabriela Luz Campos Rios', 'F', '1989-07-31'),
('71234514', 'Fernando Jose Salazar Tello', 'M', '1992-03-09'),
('71234515', 'Daniela Rocio Ponce Aguilar', 'F', '1997-01-21'),
('71234516', 'Hector Raul Chavez Medina', 'M', '1986-11-16'),
('71234517', 'Paola Andrea Delgado Nunez', 'F', '1990-08-07'),
('71234518', 'Oscar Ivan Tapia Cordova', 'M', '1984-04-13'),
('71234519', 'Natalia Belen Fuentes Lara', 'F', '1993-09-28'),
('71234520', 'Raul Enrique Pacheco Inga', 'M', '1991-06-02');

-- VENDEDORES (5 vendedores)
INSERT INTO vendedores (dni, nombres, fecha_ingreso, fecha_nacimiento) VALUES
('80001001', 'Pedro Juan Alarcon Vera', '2020-01-15', '1990-05-10'),
('80001002', 'Rosa Maria Benavides Castro', '2019-06-01', '1988-09-23'),
('80001003', 'Luis Alberto Cornejo Duran', '2021-03-10', '1992-02-14'),
('80001004', 'Sandra Patricia Figueroa Gil', '2018-11-20', '1985-12-30'),
('80001005', 'Ivan Alejandro Gonzales Hurtado', '2022-07-05', '1994-08-17');

-- PRODUCTOS (15 productos)
INSERT INTO productos (descripcion, precio, stock) VALUES
('Laptop HP Pavilion 15', 3200.00, 25),
('Monitor Samsung 24"', 850.00, 40),
('Teclado mecanico Logitech G Pro', 350.00, 60),
('Mouse inalambrico Logitech MX Master', 280.00, 55),
('Auriculares Sony WH-1000XM5', 1200.00, 30),
('Webcam Logitech C920', 250.00, 45),
('Disco SSD Kingston 1TB', 320.00, 70),
('Memoria RAM Corsair 16GB DDR4', 220.00, 80),
('Impresora Epson L3250', 950.00, 20),
('Cable HDMI 2.1 2m', 45.00, 150),
('Hub USB-C 7 en 1', 120.00, 65),
('Mousepad XXL gamer', 75.00, 90),
('Silla ergonomica gamer', 1800.00, 15),
('UPS APC 650VA', 480.00, 35),
('Tablet Samsung Galaxy Tab A8', 1100.00, 22);

-- VENTAS (30 ventas)
INSERT INTO ventas (fecha_venta, id_cliente, total_venta, estado, id_vendedor) VALUES
('2025-01-05', 1, 4100.00, 'completada', 1),
('2025-01-08', 3, 1530.00, 'completada', 2),
('2025-01-12', 5, 3550.00, 'completada', 1),
('2025-01-15', 2, 670.00, 'completada', 3),
('2025-01-18', 7, 2480.00, 'pendiente', 4),
('2025-01-22', 10, 4400.00, 'completada', 2),
('2025-01-25', 4, 1195.00, 'completada', 5),
('2025-01-28', 12, 7050.00, 'completada', 1),
('2025-02-01', 6, 545.00, 'pendiente', 3),
('2025-02-04', 8, 3520.00, 'completada', 2),
('2025-02-07', 14, 1900.00, 'completada', 4),
('2025-02-10', 9, 2640.00, 'completada', 5),
('2025-02-13', 11, 750.00, 'pendiente', 1),
('2025-02-16', 15, 5150.00, 'completada', 3),
('2025-02-19', 13, 1320.00, 'completada', 2),
('2025-02-22', 16, 4050.00, 'completada', 4),
('2025-02-25', 18, 960.00, 'pendiente', 5),
('2025-02-28', 20, 2200.00, 'completada', 1),
('2025-03-03', 17, 3840.00, 'completada', 3),
('2025-03-06', 19, 1475.00, 'completada', 2),
('2025-03-09', 1, 6400.00, 'completada', 4),
('2025-03-12', 5, 520.00, 'pendiente', 5),
('2025-03-15', 8, 2950.00, 'completada', 1),
('2025-03-18', 3, 1800.00, 'completada', 3),
('2025-03-21', 10, 3680.00, 'completada', 2),
('2025-03-24', 14, 440.00, 'pendiente', 4),
('2025-03-27', 6, 4750.00, 'completada', 5),
('2025-03-30', 11, 1570.00, 'completada', 1),
('2025-04-02', 20, 2860.00, 'completada', 3),
('2025-04-05', 7, 5200.00, 'pendiente', 2);

-- DETALLE VENTAS (~90 registros, promedio 3 por venta)
INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, precio_unitario, subtotal) VALUES
-- Venta 1 (total: 4100)
(1, 1, 1, 3200.00, 3200.00),
(1, 3, 1, 350.00, 350.00),
(1, 4, 1, 280.00, 280.00),
(1, 12, 1, 75.00, 75.00),
-- Venta 2 (total: 1530) -- actualizado
(2, 5, 1, 1200.00, 1200.00),
(2, 10, 2, 45.00, 90.00),
(2, 11, 2, 120.00, 240.00),
-- Venta 3 (total: 3550)
(3, 1, 1, 3200.00, 3200.00),
(3, 3, 1, 350.00, 350.00),
-- Venta 4 (total: 670)
(4, 3, 1, 350.00, 350.00),
(4, 7, 1, 320.00, 320.00),
-- Venta 5 (total: 2480)
(5, 5, 1, 1200.00, 1200.00),
(5, 4, 1, 280.00, 280.00),
(5, 9, 1, 950.00, 950.00),
(5, 10, 1, 45.00, 45.00),
-- Venta 6 (total: 4400)
(6, 1, 1, 3200.00, 3200.00),
(6, 5, 1, 1200.00, 1200.00),
-- Venta 7 (total: 1195)
(7, 9, 1, 950.00, 950.00),
(7, 6, 1, 250.00, 250.00),-- ajuste: 950+250=1200, necesitamos 1195
-- Venta 8 (total: 7050)
(8, 1, 2, 3200.00, 6400.00),
(8, 3, 1, 350.00, 350.00),
(8, 4, 1, 280.00, 280.00),
-- Venta 9 (total: 545)
(9, 4, 1, 280.00, 280.00),
(9, 8, 1, 220.00, 220.00),
(9, 10, 1, 45.00, 45.00),
-- Venta 10 (total: 3520)
(10, 1, 1, 3200.00, 3200.00),
(10, 7, 1, 320.00, 320.00),
-- Venta 11 (total: 1900)
(11, 13, 1, 1800.00, 1800.00),
(11, 12, 1, 75.00, 75.00),
-- Venta 12 (total: 2640) -- ajustado
(12, 15, 2, 1100.00, 2200.00),
(12, 8, 2, 220.00, 440.00),
-- Venta 13 (total: 750)
(13, 14, 1, 480.00, 480.00),
(13, 6, 1, 250.00, 250.00),
-- Venta 14 (total: 5150)
(14, 1, 1, 3200.00, 3200.00),
(14, 9, 1, 950.00, 950.00),
(14, 15, 1, 1100.00, 1100.00),-- ajuste: suma excede, corregido abajo
-- Venta 15 (total: 1320)
(15, 5, 1, 1200.00, 1200.00),
(15, 11, 1, 120.00, 120.00),
-- Venta 16 (total: 4050)
(16, 1, 1, 3200.00, 3200.00),
(16, 2, 1, 850.00, 850.00),
-- Venta 17 (total: 960)
(17, 14, 2, 480.00, 960.00),
-- Venta 18 (total: 2200)
(18, 15, 2, 1100.00, 2200.00),
-- Venta 19 (total: 3840)
(19, 1, 1, 3200.00, 3200.00),
(19, 7, 2, 320.00, 640.00),
-- Venta 20 (total: 1475)
(20, 5, 1, 1200.00, 1200.00),
(20, 12, 1, 75.00, 75.00),
(20, 11, 1, 120.00, 120.00),
(20, 10, 1, 45.00, 45.00),-- ajuste: 1200+75+120+45=1440
-- Venta 21 (total: 6400)
(21, 1, 2, 3200.00, 6400.00),
-- Venta 22 (total: 520)
(22, 4, 1, 280.00, 280.00),
(22, 8, 1, 220.00, 220.00),
-- ajuste: suma=500, se necesita 520
-- Venta 23 (total: 2950)
(23, 13, 1, 1800.00, 1800.00),
(23, 15, 1, 1100.00, 1100.00),
(23, 10, 1, 45.00, 45.00),-- ajuste: 1800+1100+45=2945
-- Venta 24 (total: 1800)
(24, 13, 1, 1800.00, 1800.00),
-- Venta 25 (total: 3680)
(25, 1, 1, 3200.00, 3200.00),
(25, 14, 1, 480.00, 480.00),
-- Venta 26 (total: 440)
(26, 8, 2, 220.00, 440.00),
-- Venta 27 (total: 4750)
(27, 1, 1, 3200.00, 3200.00),
(27, 9, 1, 950.00, 950.00),
(27, 3, 1, 350.00, 350.00),
(27, 6, 1, 250.00, 250.00),
-- Venta 28 (total: 1570)
(28, 5, 1, 1200.00, 1200.00),
(28, 3, 1, 350.00, 350.00),
-- ajuste: 1200+350=1550
-- Venta 29 (total: 2860)
(29, 13, 1, 1800.00, 1800.00),
(29, 9, 1, 950.00, 950.00),
(29, 10, 1, 45.00, 45.00),-- ajuste: 1800+950+45=2795
-- Venta 30 (total: 5200)
(30, 1, 1, 3200.00, 3200.00),
(30, 5, 1, 1200.00, 1200.00),
(30, 2, 1, 850.00, 850.00);-- ajuste: 3200+1200+850=5250

-- ============================================
-- 3. ACTUALIZAR total_venta SEGUN DETALLES REALES
-- ============================================
-- Para garantizar consistencia entre detalles y totales:

UPDATE ventas v
SET total_venta = (
    SELECT COALESCE(SUM(dv.subtotal), 0)
    FROM detalle_ventas dv
    WHERE dv.id_venta = v.id
);

-- ============================================
-- 4. VERIFICACION
-- ============================================

-- Conteo de registros
-- SELECT 'clientes' AS tabla, COUNT(*) AS registros FROM clientes
-- UNION ALL SELECT 'vendedores', COUNT(*) FROM vendedores
-- UNION ALL SELECT 'productos', COUNT(*) FROM productos
-- UNION ALL SELECT 'ventas', COUNT(*) FROM ventas
-- UNION ALL SELECT 'detalle_ventas', COUNT(*) FROM detalle_ventas;

-- Verificar que totales coincidan
-- SELECT v.id, v.total_venta, SUM(dv.subtotal) AS suma_detalles
-- FROM ventas v
-- JOIN detalle_ventas dv ON dv.id_venta = v.id
-- GROUP BY v.id, v.total_venta
-- HAVING v.total_venta <> SUM(dv.subtotal);