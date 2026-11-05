resource "aws_lb" "this" {
  name                       = "${substr(var.name, 0, 23)}-${substr(sha1(var.name), 0, 8)}"
  internal                   = false
  load_balancer_type         = "application"
  subnets                    = var.public_subnet_ids
  security_groups            = [var.security_group_id]
  drop_invalid_header_fields = true
  tags                       = var.tags
}

resource "aws_lb_target_group" "app" {
  name                 = "${substr(var.name, 0, 20)}-tg-${substr(sha1(var.name), 0, 8)}"
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = var.vpc_id
  deregistration_delay = 30
  health_check {
    enabled             = true
    path                = "/ready"
    port                = "traffic-port"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
  tags = var.tags
}

# Temporary, non-sensitive demo traffic only. TLS is a separate required production step.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
  tags = var.tags
}
